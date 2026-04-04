# Installation

## Requirements

- Python 3.9+
- Git for Windows (GitBash)
- Windows 11

## Install

```bash
git clone https://github.com/sbugera/local-dev-composer.git
cd local-dev-composer
pip install -e .
```

Installs the `ldc` command and dependencies: `rich`, `pyyaml`, `psutil`.

## Without installing (direct script)

```bash
python ldc.py <command> [options]
```

`ldc.py` at the repo root adds `src/` to `sys.path` automatically.

## Verify

```bash
ldc --help
```
