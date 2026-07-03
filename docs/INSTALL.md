# Installation

## Prerequisites

- **Linux** or **macOS**
- Network access to public FTP servers (PRIDE, jPOST, MassIVE)
- ~50 GB free disk space for typical runs (more if you enable the download stage)

## Java

Nextflow requires Java 17 or later.

```bash
# Check your Java version
java -version

# Ubuntu / Debian
sudo apt update && sudo apt install openjdk-17-jre

# macOS (Homebrew)
brew install openjdk@17
```

## Nextflow

Install Nextflow 24.04.0 or later:

```bash
# Install with curl (recommended)
curl -s https://get.nextflow.io | bash

# Move to PATH
chmod +x nextflow
sudo mv nextflow /usr/local/bin/

# Verify
nextflow -version
```

## Python 3.12

The pipeline scripts require **Python 3.12** (specified in the `uv` shebang).

```bash
# Check your version
python3 --version

# Ubuntu / Debian
sudo apt install python3.12

# macOS (Homebrew)
brew install python@3.12
```

## uv (Python package manager)

All Python scripts use `uv` in their shebang to automatically resolve dependencies. Install it system-wide:

```bash
# Standalone installer (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv

# Or via pipx
pipx install uv

# Verify
uv --version
```

No manual `pip install` is needed — `uv` downloads packages (polars, ftputil, matplotlib, numpy) on first execution and caches them.

## Verify the setup

```bash
# Test that Nextflow can parse the pipeline
nextflow run main.nf -stub-run

# Test a single Python script
uv run --with polars python3.12 bin/011_repository_to_parquet.py --help
```

## Next steps

See the [README](../README.md) for quick-start instructions and input data preparation.
