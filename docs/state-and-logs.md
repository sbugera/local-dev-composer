# State and Logs

## Runtime state

ldc persists process state to `.ldc/state.json` after every change.

```json
{
  "gateway": {
    "status": "healthy",
    "pid": 18432,
    "started_at": "2026-04-04T10:15:30+00:00",
    "last_health_check_at": "2026-04-04T10:16:00+00:00",
    "last_error": null,
    "log_file": "./logs/gateway.log"
  }
}
```

On the next `ldc` invocation the stored PIDs are loaded and reconciled against
live OS processes. Dead PIDs are automatically marked `STOPPED`.

`.ldc/state.json` is gitignored — never commit it.

## Log files

Each service gets its own log file under `log_dir` (default: `./logs/`):

| file | written by |
|------|-----------|
| `logs/<service>.log` | `up` command (stdout+stderr of the process) |
| `logs/<service>-install.log` | `install` command |

Each `up` session appends a header:

```
============================================================
[LDC] Starting 'gateway' at 2026-04-04T10:15:30+00:00
============================================================
```

Each `install` run is wrapped with a start header and a finish footer that
records the elapsed time and final status (`SUCCESS`, `FAILED (exit N)`, or
`ERROR (...)`):

```
============================================================
[LDC] Installing 'my-service' at 2026-04-04T10:15:30+00:00
[LDC] Command: gradlew clean bootJar --refresh-dependencies
============================================================
... build output ...
============================================================
[LDC] Finished 'my-service' at 2026-04-04T10:20:18+00:00
[LDC] Status: SUCCESS — elapsed 288.0s
============================================================
```

`logs/` is gitignored.

## Viewing logs

```bash
ldc logs gateway           # last 50 lines
ldc logs gateway -n 200    # last 200 lines
ldc logs gateway -f        # follow (Ctrl+C to stop)
```

Or directly:
```bash
tail -f logs/gateway.log
```

## Clearing state

```bash
rm .ldc/state.json         # reset all tracked state
rm logs/*.log              # clear all logs
```

Or for a clean restart:

```bash
ldc down
rm -f .ldc/state.json
ldc up
```
