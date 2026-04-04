# CLI Commands

```
ldc [-f FILE] [--ldc-dir DIR] <command> [options]
```

| flag | default | description |
|------|---------|-------------|
| `-f FILE` | `composer.yml` | path to config file |
| `--ldc-dir DIR` | `.ldc` | state and log directory |

---

## clone

Clone or update service repositories.

```bash
ldc clone                      # all services
ldc clone gateway user-service # specific services
ldc clone --pull               # pull latest on already-cloned repos
```

Skips services with `runtime: external` or no `repo`.

---

## check

Verify host prerequisites. Prints a table per service with PASS/FAIL and fix hints.

```bash
ldc check                      # all services
ldc check gateway              # one service
ldc check --fix                # auto-fix where possible (creates missing folders)
```

Exits `0` if all pass, `1` if any fail.

---

## install

Run each service's `install` command in its own working directory with its own environment.

```bash
ldc install                    # all services
ldc install user-service       # one service
```

Output streamed to `<log_dir>/<service>-install.log`.

---

## up

Start services in topological dependency order (dependencies first).

```bash
ldc up                         # all services
ldc up gateway user-service    # specific services + their transitive deps
ldc up --group gateway-dev     # named group (see groups in config)
ldc up --skip-checks           # skip prerequisite checks
```

Per service:
1. Check prerequisites (skippable)
2. Start process with isolated env
3. Poll health check until healthy or timeout

Shows a live Rich dashboard updating every 500ms.

---

## down

Stop services in reverse dependency order (dependents first).

```bash
ldc down                       # all services
ldc down gateway               # one service
ldc down gateway --timeout 30  # custom graceful-stop timeout (seconds)
```

Sends `SIGTERM`, waits for `--timeout`, then `SIGKILL` if still running.

---

## status

Show current status of services.

```bash
ldc status
ldc status gateway user-service
```

Reconciles against live PIDs — marks dead processes as STOPPED.

Output columns: Service | Status | PID | Started | Last Error

---

## logs

View or follow a service log file.

```bash
ldc logs gateway               # last 50 lines
ldc logs gateway -n 100        # last 100 lines
ldc logs gateway -f            # follow (tail -f), Ctrl+C to stop
```

---

## env

Show the fully-resolved environment for a service after all merging (system → env_files → inline env).

```bash
ldc env gateway                    # variables from env_files + inline env
ldc env gateway --all              # also include inherited system variables
ldc env gateway --filter SPRING    # only variables starting with SPRING
```

Each row shows the variable name, value, and where it came from (`inline`, filename, or `system`).

---

## doctor

Full diagnostic — checks everything and prints a numbered action list.

```bash
ldc doctor
ldc doctor gateway             # specific service only
```

Checks:
1. All prerequisites (same as `check`)
2. Git clone status for each service
3. Process alive status + log reference if crashed
4. Summary action list with exact commands to run
