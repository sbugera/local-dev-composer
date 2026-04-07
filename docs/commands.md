# CLI Commands

```
ldc [-f FILE] [--ldc-dir DIR] [--workers N] [--no-interactive] <command> [options]
```

| flag | default | description |
|------|---------|-------------|
| `-f FILE` | `composer.yml` | path to config file |
| `--ldc-dir DIR` | `.ldc` | state and log directory |
| `--workers N` | from `composer.yml` | max parallel threads for clone / install / up; overrides `workspace.workers` |
| `--no-interactive` | off | disable the interactive TUI dashboard; use plain Rich output instead |

## Interactive dashboard

When running `up` or `bootstrap` in a real terminal (TTY), ldc automatically launches
an interactive pseudo-GUI built with [Textual](https://textual.textualize.io/):

```
┌─ ldc — local-dev-composer ──────────────────────────────────┐
│  Service         Status     PID    Started    Runtime        │
│  postgres        HEALTHY    1234   10:30:01   external       │  ← arrow keys select
│  gateway       ▶ STARTING   —      —          java           │
│  user-service    PENDING    —      —          node           │
├── Details ──── Logs ────────────────────────────────────────│
│  Service:  gateway  ·  Runtime: java  ·  Depends: postgres  │
│  Status:   ◌ starting…                                       │
└─ [q] Quit  [↑↓] Select service  [Tab] Switch panel ─────────┘
```

**Controls**: `↑`/`↓` navigate the service table; `Tab` switches between the
Details and Logs tabs; `q` exits the dashboard.

**Logs tab**: streams the selected service's log file in real time (last 200 lines
on open, then follows new output).

**Requires**: `pip install "local-dev-composer[ui]"` (adds `textual>=0.50`).

Disable with `ldc --no-interactive up` or set `NO_INTERACTIVE=1` is not needed —
the plain Rich dashboard is used automatically when stdout is not a TTY (CI, pipes).

---

## bootstrap

Full onboarding sequence: clone → install → start. The single command a new developer needs.

```bash
ldc bootstrap                        # everything
ldc bootstrap --group gateway-dev    # minimum services for one feature area
ldc bootstrap --skip-checks          # skip prerequisite checks
ldc --workers 8 bootstrap            # clone, install, and start with 8 parallel workers
ldc --no-interactive bootstrap       # plain Rich output instead of interactive TUI
```

If a service fails to clone, it is skipped in install and start.
If a service fails to install, it is skipped in start.
Other services always continue.

---

## clone

Clone or update service repositories.

```bash
ldc clone                      # all services (4 parallel workers by default)
ldc clone gateway user-service # specific services
ldc clone --pull               # pull latest on already-cloned repos
ldc --workers 1 clone          # sequential (one at a time)
```

Clones always run in parallel regardless of `depends_on`. Use `--workers 1` to force sequential.
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
ldc install                    # all services (4 parallel workers by default)
ldc install user-service       # one service
ldc --workers 1 install        # sequential (one at a time)
```

Installs always run in parallel regardless of `depends_on`. Use `--workers 1` to force sequential.
Output streamed to `<log_dir>/<service>-install.log`.

---

## up

Start services in dependency order. Services with no dependency on each other start in parallel.

```bash
ldc up                         # all services (4 parallel workers by default)
ldc up gateway user-service    # specific services + their transitive deps
ldc up --group gateway-dev     # named group (see groups in config)
ldc up --skip-checks           # skip prerequisite checks
ldc --workers 1 up             # sequential, one service at a time
ldc --workers 8 up             # up to 8 services starting concurrently
ldc --no-interactive up        # plain Rich output instead of interactive TUI
```

Per service:
1. Check prerequisites (skippable)
2. Start process with isolated env
3. Poll health check until healthy or timeout

Parallelism follows dependency levels: all services in the same level (no dependency between
them) start concurrently. ldc waits for all services in a level to finish before advancing to
the next level. If a dependency fails, all services that depend on it are skipped.

When stdout is a TTY and `textual` is installed, shows an interactive TUI dashboard
(see [Interactive dashboard](#interactive-dashboard) above).
Otherwise shows a live Rich table updating every 500ms.

---

## down

Stop services.

```bash
ldc down                               # all services, reverse dependency order (dependents first)
ldc down gateway                       # only gateway — dependencies are not touched
ldc down gateway user-service          # only these two, in safe order relative to each other
ldc down gateway --timeout 30          # custom graceful-stop timeout (seconds)
```

When stopping **specific services**, only the named services are stopped — their dependencies are left running (other services may still need them).

When stopping **all services** (no args), reverse dependency order is used so dependents are stopped before the services they rely on.

Stops gracefully: sends `SIGTERM` to child processes then the parent, waits up to `--timeout` seconds, then force-kills (`SIGKILL`) anything still alive.

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

## restart

Stop then start services without reinstalling.

```bash
ldc restart backend                    # restart one service
ldc restart backend gateway            # restart multiple services
ldc restart --group fullstack          # restart a named group
ldc restart backend --skip-checks      # skip prerequisite checks on start
ldc restart                            # restart ALL services
```

Stops in reverse dependency order, starts in dependency order.

---

## rebuild

Stop, reinstall, then start services. Use this after code changes.

```bash
ldc rebuild backend                    # rebuild one service
ldc rebuild backend gateway ui         # rebuild multiple services
ldc rebuild --group fullstack          # rebuild a named group
ldc rebuild backend --skip-checks      # skip prerequisite checks on start
ldc rebuild                            # rebuild ALL services (prompts for confirmation)
```

Sequence per run: stop all targets → install each in dependency order → start successfully installed services.
If `install` fails for a service, its `up` is skipped but other services continue.

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
