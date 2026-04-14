# Leader-Follower Concurrency Design

## The Problem

Engram uses embedded Qdrant as its vector database. Embedded Qdrant acquires an **exclusive file lock** on the data directory (`~/.engram/data/`) when a process starts, and holds it for the entire process lifetime. This means:

- Only **one engram process** can access the data directory at a time
- A second process attempting to open the same directory crashes immediately with `RuntimeError: Storage folder ... is already accessed by another instance`
- This affects **all modes**: stdio, serve, or any combination

### Why this matters

Claude Code spawns a new stdio MCP process per session. A developer with two terminal sessions, or one session plus the web UI, will hit this lock. The current workaround is to use HTTP serve mode (one shared server), but this defeats the purpose of the stdio transport — which is the recommended zero-config installation path (`claude mcp add engram -- uvx engramd`).

### What we want

Multiple concurrent `engramd` stdio processes, each serving a separate Claude Code session, all sharing the same preference data. No user configuration required.

## Solution: Leader-Follower Pattern

The first engram process to start becomes the **leader** — it owns Qdrant and exposes an internal API. Subsequent processes become **followers** — they detect the leader and proxy all preference operations through it. From Claude Code's perspective, every process behaves identically.

```
                    Claude Code              Claude Code              Claude Code
                    Session 1                Session 2                Session 3
                        |                        |                        |
                    [stdio]                  [stdio]                  [stdio]
                        |                        |                        |
                  engramd (LEADER)         engramd (FOLLOWER)     engramd (FOLLOWER)
                    |       |                    |                        |
              [Qdrant DB]  [Internal API]--------+------------------------+
              ~/.engram/    localhost:3778
              data/
```

## Detailed Algorithm

### Startup Sequence

```
                        engramd process starts
                                |
                        Read lock file
                    (~/.engram/leader.lock)
                                |
                    +-------exists?-------+
                    |                     |
                    no                   yes
                    |                     |
            Try acquire file          Read address
            lock (flock)              from lock file
                    |                     |
            +---acquired?---+      Probe: GET /health
            |               |      on that address
           yes              no            |
            |               |      +---alive?---+
            |               |      |            |
            |               |     yes           no
            |               |      |            |
        BECOME LEADER   WAIT &     |      Stale lock!
            |           RETRY      |      Remove it,
            |               |      |      go back to
            |               +------+      "Try acquire"
            |                      |
    1. Start internal API          |
       on available port           |
    2. Write lock file:            |
       {"pid": N,            BECOME FOLLOWER
        "port": P,                 |
        "started": T}       1. Create HTTP proxy
    3. Open Qdrant              PreferenceStore
    4. Start MCP stdio       2. Start MCP stdio
    5. On exit: cleanup         (uses proxy store)
       lock file
```

### Lock File

**Location:** `~/.engram/leader.lock`

**Contents (JSON):**
```json
{
  "pid": 12345,
  "port": 3778,
  "started": "2026-04-14T15:30:00Z"
}
```

**Lifecycle:**
- Created atomically by the leader using `fcntl.flock()` exclusive lock
- Read by followers to discover the leader's address
- Removed by the leader on clean exit (via `atexit` + signal handlers)
- Stale locks detected by probing the health endpoint

### Leader Responsibilities

```
    LEADER PROCESS
    ==============

    +-----------------------+
    |   MCP stdio server    |  <-- Claude Code talks to this
    |   (same as today)     |
    +-----------+-----------+
                |
        PreferenceStore
        (Mem0 + Qdrant)
                |
    +-----------+-----------+
    |  Internal HTTP API    |  <-- Followers talk to this
    |  localhost:3778       |
    |                       |
    |  GET  /health         |
    |  POST /preferences    |
    |  GET  /preferences    |
    |  GET  /preferences/:id|
    |  PUT  /preferences/:id|
    |  DEL  /preferences/:id|
    |  POST /search         |
    |  GET  /scopes         |
    |  GET  /tags           |
    +-----------------------+
```

The internal API reuses the existing REST route handlers. It binds to `localhost` only (not exposed externally). Port selection:
- Default: `3778` (one above the public serve port)
- If taken: try `3779`, `3780`, etc.
- Write the actual port to the lock file

### Follower Responsibilities

```
    FOLLOWER PROCESS
    ================

    +-----------------------+
    |   MCP stdio server    |  <-- Claude Code talks to this
    |   (same tools/schema) |
    +-----------+-----------+
                |
        ProxyPreferenceStore
        (HTTP client)
                |
        Calls leader at
        localhost:3778
```

The follower creates a `ProxyPreferenceStore` that implements the same `PreferenceStore` interface but makes HTTP calls to the leader instead of accessing Qdrant. From the MCP layer's perspective, the store is interchangeable.

### Stale Lock Detection

A lock file can become stale if the leader crashes without cleanup (e.g., `kill -9`, power loss).

**Detection:**
1. Follower reads lock file, gets `pid` and `port`
2. Follower calls `GET http://localhost:{port}/health` with a 2-second timeout
3. If the health check succeeds: leader is alive, proceed as follower
4. If it fails (connection refused, timeout): stale lock
5. Optionally: verify the PID is still running via `os.kill(pid, 0)`

**Recovery:**
1. Remove the stale lock file
2. Retry the startup sequence from the beginning
3. This process (or another concurrent one) becomes the new leader

### Graceful Leader Shutdown

```
    Leader receives SIGTERM / SIGINT / exits normally
                        |
                Register via atexit + signal handlers
                        |
                1. Stop accepting new internal API requests
                2. Wait for in-flight requests (up to 5s)
                3. Close Qdrant
                4. Remove lock file
                5. Release flock
```

After the leader exits, the next follower that starts (or retries) will become the new leader. Existing followers will get connection errors and should:
1. Log a warning
2. Retry the request once (a new leader may have started)
3. If still failing, return an error to Claude Code (which will retry)

### Leader Handoff (Advanced, Future)

In the basic implementation, when a leader exits, existing followers lose their backend until a new leader starts. For a smoother experience:

1. Leader announces shutdown on the internal API: `POST /shutdown-notice`
2. One follower promotes itself: acquires flock, opens Qdrant, starts internal API
3. Other followers switch to the new leader's address
4. Original leader exits

This is complex and not needed for v1. The basic "retry and a new leader will appear" approach is sufficient since Claude Code sessions are ephemeral.

## File Changes

### New files:
- `src/engram/concurrency/lock.py` — Lock file management (acquire, read, detect stale, cleanup)
- `src/engram/concurrency/leader.py` — Internal API server startup, binds to localhost
- `src/engram/concurrency/proxy.py` — `ProxyPreferenceStore` (HTTP client implementing `PreferenceStore`)
- `tests/test_concurrency/` — Tests for lock, leader, proxy

### Modified files:
- `src/engram/main.py` — `run_stdio()` updated to use startup sequence (try leader, fall back to follower)
- `src/engram/storage/base.py` — No changes needed (ProxyPreferenceStore implements the same interface)

### Untouched:
- MCP tool definitions
- CLI parser
- Serve mode (runs its own server, unaffected)
- Setup command
- Web UI

## Edge Cases

| Scenario | Behavior |
|---|---|
| Leader crashes (kill -9) | Stale lock detected by health probe, next process becomes leader |
| Two processes start simultaneously | `flock()` ensures only one acquires the lock; the other retries and becomes follower |
| Leader's port is taken by another app | Leader tries next port (3779, 3780, ...) and writes actual port to lock file |
| Follower starts, no leader exists | Follower becomes leader (normal startup path) |
| All sessions close, new one starts | Fresh start, becomes leader (no lock file exists) |
| `engramd serve` running + stdio session | Serve mode should also participate in the protocol (future), or document mutual exclusion |

## Constraints

- Internal API binds to `localhost` only — never externally accessible
- Lock file uses `fcntl.flock()` — POSIX only (macOS + Linux). Windows would need a different mechanism.
- Follower adds ~1-2ms latency per preference operation (localhost HTTP round trip) — negligible
- No data migration or schema changes needed — the data layer is unchanged

## Testing Strategy

1. **Unit tests:** Lock acquisition, stale detection, proxy store HTTP calls (mocked)
2. **Integration tests:** Two processes, first becomes leader, second becomes follower, both serve MCP
3. **Chaos tests:** Kill leader mid-request, verify follower recovers
4. **Manual test:** Open two Claude Code sessions, add preferences from both, verify they share data
