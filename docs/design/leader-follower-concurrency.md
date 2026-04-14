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

## Solution: Single-Port Leader Election

A single, well-known port (default `3778`, user-configurable) acts as the coordination point. The OS guarantees only one process can bind to a port — this is the lock. No port scanning, no ranges, no ambiguity.

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

### Why single-port, not a port range

A port range introduces a **split-brain bug**:

1. Port 3778 is occupied by a non-engram process (e.g. a dev server)
2. Engram tries 3778, fails health check, skips it, becomes leader on 3779
3. The non-engram process on 3778 dies — port 3778 is now free
4. A new engram session starts, scans from 3778, finds it free, becomes leader on 3778
5. **Two leaders exist** (3778 and 3779), each with their own Qdrant — but only one can actually hold the Qdrant lock

A single port makes this impossible. There is exactly one coordination point. You're either the leader on that port, a follower talking to it, or you get a clear error.

### Why port-based, not file-based

| Lock files | Port binding |
|---|---|
| Must be cleaned up on exit | OS reclaims port automatically when process dies |
| Stale after crash (kill -9) | No stale state possible — port is free immediately |
| Needs `fcntl.flock()` (POSIX only) | Works on all platforms |
| Requires atexit + signal handlers | No cleanup code needed |
| Race conditions on read/write | OS-level atomic bind |

## Detailed Algorithm

### Startup Sequence

```
                     engramd stdio process starts
                                |
                     Try to bind to port 3778
                                |
                     +------success?------+
                     |                    |
                    yes                   no (address in use)
                     |                    |
               BECOME LEADER        Call GET /health
                     |               on localhost:3778
                     |                    |
               1. Open Qdrant    +---is it engram?---+
               2. Start internal |                   |
                  API on :3778  yes                  no
               3. Start MCP      |                   |
                  stdio      BECOME FOLLOWER    LOG ERROR
                                 |              "Port 3778 in use
                           1. Create proxy       by another process.
                              PreferenceStore    Configure a different
                           2. Start MCP stdio    port in ~/.engram/
                              (uses proxy)       config.yaml"
```

### Three outcomes — no ambiguity

| Port state | Health check | Result |
|---|---|---|
| Free | N/A | Bind it. You're the leader. |
| Taken | Returns `{"service": "engramd"}` | It's us. You're a follower. |
| Taken | Anything else (404, timeout, non-engram JSON, connection refused by firewall) | Not us. Error — tell user to change port. |

### Health Endpoint & Engram Identification

The leader's internal API health endpoint returns an engram-specific response:

```
GET http://localhost:3778/health

Response (200 OK):
{
  "service": "engramd",
  "role": "leader",
  "pid": 12345,
  "version": "0.1.1",
  "port": 3778,
  "uptime_seconds": 142
}
```

**Identification rules:**
1. Response must be valid JSON
2. `"service"` field must equal `"engramd"` exactly
3. If either check fails → this port is NOT an engram leader → error

### Configuration

The coordination port is configured in `~/.engram/config.yaml`:

```yaml
coordination:
  port: 3778  # default
```

This is the **only** configuration needed. If a user has something else on 3778, they change this one value and all engram processes (leader + followers) use the new port.

### Leader Responsibilities

```
    LEADER PROCESS
    ==============

    +-----------------------+
    |   MCP stdio server    |  <-- Claude Code talks to this (stdin/stdout)
    |   (same as today)     |
    +-----------+-----------+
                |
        PreferenceStore
        (Mem0 + Qdrant)
                |
    +-----------+-----------+
    |  Internal HTTP API    |  <-- Followers talk to this
    |  localhost:3778       |
    |  (127.0.0.1 only)    |
    |                       |
    |  GET  /health         |  Returns {"service":"engramd", ...}
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

The internal API reuses the existing REST route handlers. It binds to `127.0.0.1` only (never `0.0.0.0`). The internal API runs in a background thread so it doesn't block the MCP stdio event loop.

### Follower Responsibilities

```
    FOLLOWER PROCESS
    ================

    +-----------------------+
    |   MCP stdio server    |  <-- Claude Code talks to this (stdin/stdout)
    |   (same tools/schema) |
    +-----------+-----------+
                |
        ProxyPreferenceStore
        (HTTP client to leader)
                |
        Calls leader at
        localhost:3778
```

The follower creates a `ProxyPreferenceStore` that implements the same `PreferenceStore` interface but makes HTTP calls to the leader. From the MCP layer's perspective, the store is interchangeable — same methods, same return types.

### Leader Crash Recovery

When a leader process dies (even `kill -9`):

1. OS immediately releases port 3778
2. Existing followers get connection errors on next request
3. Next `engramd` process to start tries to bind 3778 → succeeds → becomes leader
4. Existing followers retry → new leader is on the same port → works transparently

```
    Timeline:

    t=0   Leader on :3778, Follower A, Follower B
    t=1   Leader crashes (kill -9)
    t=1   Port 3778 is immediately free
    t=2   Follower A tries to call leader -> connection refused
    t=2   Follower A logs warning, returns error to Claude Code
    t=3   New session starts engramd -> bind :3778 succeeds -> becomes leader
    t=4   Follower A retries -> succeeds (new leader is up on same port)
```

Because the port never changes, followers don't need to "rediscover" anything. They just retry the same address.

### Follower Resilience

When a follower's request to the leader fails:

```
    Follower makes request to leader at :3778
                |
         +---success?---+
         |              |
        yes             no
         |              |
      Return         Check /health on :3778
      result                |
                     +---is it engram?---+
                     |                   |
                    yes                  no / refused
                     |                   |
               Retry request       Return error
               (transient failure) to Claude Code
                                   (leader is down,
                                    it will recover
                                    when a new session
                                    starts)
```

No rescanning needed. The port is fixed — either the leader is there or it isn't.

## File Changes

### New files:
- `src/engram/concurrency/discovery.py` — Port probe, health check, engram identification
- `src/engram/concurrency/leader.py` — Internal API server startup on coordination port
- `src/engram/concurrency/proxy.py` — `ProxyPreferenceStore` (HTTP client implementing `PreferenceStore`)
- `tests/test_concurrency/` — Tests for discovery, leader, proxy, resilience

### Modified files:
- `src/engram/main.py` — `run_stdio()` uses discovery to decide leader vs follower
- `src/engram/core/models.py` — Add `coordination.port` to config model
- `src/engram/api/routes/health.py` — Add `service: "engramd"` to health response

### Untouched:
- MCP tool definitions
- CLI parser
- Serve mode (runs its own server, unaffected)
- Setup command
- Web UI
- PreferenceStore interface

## Edge Cases

| Scenario | Behavior |
|---|---|
| Leader crashes (kill -9, power loss) | Port freed by OS instantly. Next process becomes leader on the same port. No stale state. |
| Two processes start simultaneously | OS guarantees only one can bind. Loser gets "address in use", checks health, finds the winner, becomes follower. |
| Non-engram app on port 3778 | Health check returns non-engram response. Clear error: "Port 3778 is in use by another process. Set a different port in ~/.engram/config.yaml". |
| All sessions close, new one starts | Port 3778 is free. Bind succeeds. Become leader. Normal path. |
| `engramd serve` running + stdio session | Serve mode on port 3777 doesn't conflict with coordination port 3778. But both try to open Qdrant. Serve mode should participate in the protocol in the future. For now: document that `engramd serve` and stdio can't run simultaneously. |
| Follower outlives leader | Follower gets connection errors. Returns error to Claude Code. Next new session will become leader, and follower's retries will succeed. |
| User changes coordination port | All processes (leader + followers) read from same config. Change takes effect on next process start. Existing processes continue on old port until restarted. |

## Constraints

- Internal API binds to `127.0.0.1` only — never externally accessible
- Coordination port configurable via `~/.engram/config.yaml` (`coordination.port`, default `3778`)
- Follower adds ~1-2ms latency per preference operation (localhost HTTP round trip) — negligible
- No data migration or schema changes needed — the data layer is unchanged
- Works on macOS, Linux, and Windows (no POSIX-specific file locking)

## Testing Strategy

1. **Unit tests:** Health probe with mocked responses, engram identification logic, proxy store HTTP calls
2. **Integration tests:** Start two processes, verify first becomes leader and second becomes follower, both serve MCP tools correctly
3. **Crash recovery tests:** Start leader + follower, kill leader, verify follower detects failure, start new process as leader, verify follower reconnects
4. **Port conflict tests:** Start a non-engram HTTP server on 3778, verify engram logs clear error message
5. **Manual test:** Open two Claude Code sessions with `uvx engramd`, add preferences from both, verify they share data
