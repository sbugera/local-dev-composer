# Prerequisites

ldc checks host conditions before starting a service and reports exactly what
to fix. All checks run without raising exceptions — failures are collected and
displayed together.

## Supported checks

### Runtime versions

```yaml
requires:
  java: ">=17"
  python: ">=3.9"
  node: ">=18"
  dotnet: ">=6"
```

Operators: `>=`, `>`, `<=`, `<`, `==`

Java version is read from `java -version` (stderr). Others from `--version` stdout.

### Commands on PATH

```yaml
requires:
  commands: [mvn, curl, psql]
```

Uses `shutil.which()`. Fix hint: `where mvn` to diagnose on Windows.

### Environment variables

```yaml
requires:
  env_vars: [JAVA_HOME]
```

Checks presence and non-empty value.

### Folders

```yaml
requires:
  folders:
    - C:/data/my-service
    - C:/logs/my-service
```

`ldc check --fix` creates missing folders automatically.

### Files

```yaml
requires:
  files:
    - C:/config/keystore.jks
    - C:/certs/ca.pem
```

Must exist; no auto-fix — user must provide the file.

### Free ports

```yaml
requires:
  ports_free: [8080, 8443]
```

Attempts `socket.bind()`. If occupied, shows:
```
netstat -ano | findstr :8080
```

## Running checks

```bash
ldc check                  # check all services, show report
ldc check gateway          # check one service
ldc check --fix            # auto-fix fixable items (missing folders)
```

Exit code `0` = all passed, `1` = any failed.

## Example output

```
╭─ gateway ──────────────────────────────────────────────────────╮
│ Check                  Result  Details              Fix hint   │
│ java runtime           PASS    java 17.0.9 — >=17              │
│ command 'mvn'          PASS    found on PATH                   │
│ env var 'JAVA_HOME'    PASS    $JAVA_HOME is set               │
│ folder 'C:/data/gw'    FAIL    does NOT exist    mkdir -p ...  │
│ port 8080 free         PASS    Port 8080 is free               │
╰────────────────────────────────────────────────────────────────╯
```
