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

## Solution: Port-Based Leader Discovery

Instead of lock files, we use the **port itself as the lock mechanism**. The OS guarantees only one process can bind to a port. A well-known port range (`3778-3787`) acts as the discovery mechanism. Health responses include an engram identifier to distinguish our process from unrelated services.

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
                    Scan discovery ports 3778-3787
                    For each port, call GET /health
                                |
                +-----found engram leader?-----+
                |                              |
               yes                             no
                |                              |
          Read leader port             Try bind to 3778
          from health response                 |
                |                     +----success?----+
                |                     |                |
          BECOME FOLLOWER        BECOME LEADER    Try 3779...3787
                |                     |                |
          1. Create proxy        1. Open Qdrant   +--success?--+
             PreferenceStore     2. Start internal |            |
          2. Start MCP stdio        API on port   yes       FAIL
             (uses proxy)        3. Start MCP     |      (log error,
                                    stdio         |       run without
                                                  |       concurrency)
                                             BECOME LEADER
```

### Health Endpoint & Engram Identification

The internal API health endpoint returns an engram-specific response that distinguishes it from any other service that might be running on the same port:

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
3. If either check fails, this port is not an engram leader — skip it

This prevents false positives from other services (web servers, databases, dev tools) that might happen to be on one of the discovery ports.

### Discovery Port Range

**Ports:** `3778` through `3787` (10 ports)

**Why a range, not a single port:**
- Another application might occupy port 3778
- The range gives engram 10 chances to find or become a leader
- 10 ports is enough — you won't have 10 non-engram services on these exact ports

**Scan order:**
- Followers scan `3778, 3779, ..., 3787` looking for an existing leader
- Leaders try to bind starting at `3778`, incrementing on failure
- Both use the same order, so the first available port wins

```
    FOLLOWER SCAN                    LEADER BIND

    3778: GET /health                3778: try bind()
      -> not engram, skip              -> address in use, skip
    3779: GET /health                3779: try bind()
      -> connection refused, skip      -> success! LEADER on 3779
    3780: GET /health
      -> {"service":"engramd"} !
      -> found leader on 3780
```

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
    |  localhost:{port}     |
    |  (not externally      |
    |   accessible)         |
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
        localhost:{discovered_port}
```

The follower creates a `ProxyPreferenceStore` that implements the same `PreferenceStore` interface but makes HTTP calls to the leader. From the MCP layer's perspective, the store is interchangeable — same methods, same return types.

### Leader Crash Recovery

No special handling needed. When a leader process dies (even `kill -9`):

1. OS immediately releases the port
2. The port starts returning "connection refused"
3. Existing followers get connection errors on next request
4. Next `engramd` process to start scans ports, finds no leader, becomes leader
5. Existing followers can retry failed requests — if a new leader appeared on the same port, it works transparently

```
    Timeline:

    t=0   Leader on :3778, Follower A, Follower B
    t=1   Leader crashes (kill -9)
    t=1   Port 3778 is immediately free
    t=2   Follower A tries to call leader -> connection refused
    t=2   Follower A logs warning, returns error to Claude Code
    t=3   New session starts engramd -> scans ports -> no leader -> becomes leader on :3778
    t=4   Follower A retries -> succeeds (new leader is up)
```

### Follower Resilience

When a follower's request to the leader fails:

```
    Follower makes request to leader
                |
         +---success?---+
         |              |
        yes             no
         |              |
      Return         Rescan ports 3778-3787
      result         for engram leader
                        |
                 +---found?---+
                 |            |
                yes           no
                 |            |
           Retry request   Return error
           to new/same     to Claude Code
           leader          (it will retry)
```

## File Changes

### New files:
- `src/engram/concurrency/discovery.py` — Port scanning, health probing, engram identification
- `src/engram/concurrency/leader.py` — Internal API server startup on discovery port
- `src/engram/concurrency/proxy.py` — `ProxyPreferenceStore` (HTTP client implementing `PreferenceStore`)
- `tests/test_concurrency/` — Tests for discovery, leader, proxy, resilience

### Modified files:
- `src/engram/main.py` — `run_stdio()` uses discovery to decide leader vs follower
- `src/engram/api/routes/health.py` — Add `service: "engramd"` to health response (internal API uses extended version)

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
| Leader crashes (kill -9, power loss) | Port freed by OS instantly. Next process becomes leader. No stale state. |
| Two processes start simultaneously | OS guarantees only one can bind to a port. Loser gets "address in use", scans for the winner, becomes follower. |
| Non-engram app on port 3778 | Health probe returns non-engram response (no `"service": "engramd"`). Skip port, try 3779. |
| All 10 discovery ports occupied by other apps | Fail gracefully with clear error: "Could not find or become leader on ports 3778-3787". Run in solo mode (direct Qdrant, no concurrency). |
| All sessions close, new one starts | No leader found during scan. Bind to 3778. Become leader. Normal path. |
| `engramd serve` running + stdio session | Serve mode on port 3777 doesn't conflict with internal API on 3778+. But both try to open Qdrant. Serve mode should participate in the protocol in the future. For now: document that `engramd serve` and stdio can't run simultaneously. |
| Follower outlives leader | Follower detects connection error, rescans. If no new leader, follower could promote itself (try binding). |
| 11+ concurrent sessions | Only 10 discovery ports. 11th process can't find a free port to be leader, but it can still be a follower to an existing leader. Only a problem if somehow 10 non-engram services occupy all ports AND no leader exists. Extremely unlikely. |

## Constraints

- Internal API binds to `127.0.0.1` only — never externally accessible
- Discovery port range `3778-3787` is configurable via `~/.engram/config.yaml` for edge cases
- Follower adds ~1-2ms latency per preference operation (localhost HTTP round trip) — negligible
- No data migration or schema changes needed — the data layer is unchanged
- Works on macOS, Linux, and Windows (no POSIX-specific file locking)

## Testing Strategy

1. **Unit tests:** Port scanning with mocked HTTP responses, engram identification logic, proxy store HTTP calls
2. **Integration tests:** Start two processes, verify first becomes leader and second becomes follower, both serve MCP tools correctly
3. **Crash recovery tests:** Start leader + follower, kill leader, verify follower detects failure, start new process as leader, verify follower reconnects
4. **False positive tests:** Start a non-engram HTTP server on 3778, verify engram skips it and uses 3779
5. **Manual test:** Open two Claude Code sessions with `uvx engramd`, add preferences from both, verify they share data
