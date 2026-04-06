# Installation

## Requirements

- Python 3.9+
- Git for Windows (GitBash)
- Windows

## Install from PyPI

```bash
pip install local-dev-composer
```

Installs the `ldc` command and dependencies: `rich`, `pyyaml`, `psutil`.

## Verify

```bash
ldc --help
```

---

## If `ldc` is not recognised after install

This happens when `pip install --user` is used and Python's user Scripts directory
is not on your PATH. Choose one of the following:

### Option 1 — Add user Scripts to PATH (recommended)

Add this directory to your user PATH via System Properties → Environment Variables:

```
C:\Users\<YourName>\AppData\Roaming\Python\Python3XX\Scripts
```

Then restart your terminal. `ldc` will work from anywhere.

### Option 2 — Run via `python -m`

No PATH change needed. Use everywhere you would use `ldc`:

```bash
python -m ldc up
python -m ldc status
```

### Option 3 — Install without `--user` (admin terminal)

Opens an elevated terminal and installs to the global Scripts directory,
which is already on PATH:

```bash
pip install local-dev-composer
```

### Option 4 — Install inside a virtual environment

```bash
python -m venv ldc-env
ldc-env\Scripts\activate
pip install local-dev-composer
ldc --help
```

The venv's Scripts directory is activated automatically — no PATH changes needed.

---

## Install from source

```bash
git clone https://github.com/sbugera/local-dev-composer.git
cd local-dev-composer
pip install -e .
```

## Without installing (direct script)

```bash
python ldc.py <command> [options]
```

`ldc.py` at the repo root adds `src/` to `sys.path` automatically.
