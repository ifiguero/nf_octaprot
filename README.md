# nf_octaprot — Proteomics Repository Aggregation Pipeline

```bash
nextflow run main.nf -resume
```

A Nextflow DSL2 pipeline that discovers proteomics datasets from public FTP repositories (PRIDE, jPOST, MassIVE), catalogs their files, splits them into stratified batches, and generates summary SQL dumps with visualisation charts.

---

## Project overview

This pipeline automates the process of:

1. **Discovering** datasets listed in input CSV files and connecting to their FTP servers
2. **Cataloging** all files (sample data + auxiliary files) found at each repository
3. **Splitting** labeled replicates into size-balanced, stratified batches for downstream processing
4. **Dumping** silver-layer data into portable SQL scripts with accompanying pie-chart breakdowns

Two pipeline stages (Normalize and Ingest Bronze) are scaffolded but **currently disabled** — see the workflow overview below.

---

## Repository structure

```
├── main.nf                     # Entry point — DSL2 workflow
├── nextflow.config             # Pipeline configuration
├── nextflow-not.config         # Alternative config with process-level publishDir
├── LICENSE                     # GNU Affero GPL v3
├── README.md
│
├── input/
│   ├── stage01_scrap/          # CSV files listing repositories to scan
│   ├── stage02_batch/          # CSV files with labeled replicate annotations
│   ├── stage03_dataset/        # (reserved) Dataset manifests
│   └── stage99_dumpdb/         # Dump request files
│
├── output/
│   ├── silver/                 # Parquet silver-layer tables
│   │   ├── repositories/
│   │   ├── files/
│   │   ├── replicates/
│   │   ├── datasets/           
│   ├── bronze/                 # (reserved) Downloaded raw data (.mzML.gz etc.)
│   └── dump/                   # Generated CSV summaries, batch splits, SQL, charts
│       ├── 01repo/             # Repository summary CSVs
│       ├── 02batch/            # Stratified batch splits
│       └── 99sqldump/          # SQL dumps and PNG breakdown charts
│
├── workflows/                  # Workflow definitions with inlined processes
│   ├── 01repository_scrap.nf
│   ├── 02batch_split.nf
│   ├── 03normalize.nf          # Disabled — scripts are empty stubs
│   ├── 04ingest_bronze.nf      # Disabled — scripts are empty stubs
│   └── 99dump.nf
│
├── bin/                        # Python scripts executed by processes
│   ├── 011_repository_to_parquet.py
│   ├── 012_repository_scrap.py
│   ├── 013_repository_summary_csv.py
│   ├── 021_load_replicates.py
│   ├── 022_batch_split.py
│   ├── 031_batch_work_load.py       # Empty stub
│   ├── 032_download_transcode_bronze.py  # Empty stub
│   ├── 041_ingest_bronze.py         # Empty stub
│   ├── 991_parquet_to_sql_dump.py
│   └── 992_dump_breakdown.py
│
├── conf/
│   ├── profiles.config         # Execution profiles (local / workstation / server / debug)
│   └── resources.config        # Per-process CPU / memory / time defaults
│
├── lib/
│   └── silver_model.py         # Canonical silver-layer data-model reference
│
├── assets/                     # Sample pipeline input data and archives
│   ├── raw/                    # Master repository CSV used to seed stage01 inputs
│   ├── stage01_scrap.zip       # Sample stage-01 input CSVs (extract to input/)
│   └── stage02_batch.zip       # Sample stage-02 input CSVs (extract to input/)
└── modules/                    # Empty placeholder files (processes are in workflows/)
```

---

## Requirements

| Dependency | Minimum version | Notes |
|---|---|---|
| Nextflow | 24.04.0 | DSL2 enabled |
| Java | 17+ | Required by Nextflow |
| Python | 3.12 | Runtime for all `bin/` scripts |
| [uv](https://docs.astral.sh/uv/) | — | Python package manager (used in shebangs) |

Python dependencies are declared inline via `uv` shebangs and are resolved automatically at runtime:

- **polars** — all data processing scripts
- **ftputil** — `012_repository_scrap.py`
- **matplotlib**, **numpy** — `992_dump_breakdown.py`

---

## Quick start

### 1. Install dependencies

See [INSTALL.md](docs/INSTALL.md) for detailed setup.

### 2. Prepare input data

Place repository CSVs in `input/stage01_scrap/` and annotation CSVs in `input/stage02_batch/`. Example files are already present:

```bash
ls input/stage01_scrap/
# ftp.jpostdb.org.csv  ftp.pride.ebi.ac.uk.csv
```

Sample input data is bundled in `assets/` — extract the archives to populate both input directories:

```bash
unzip -o assets/stage01_scrap.zip -d input/
unzip -o assets/stage02_batch.zip -d input/
```

### 3. Run the pipeline

```bash
nextflow run main.nf
```

Resume from a cached run:

```bash
nextflow run main.nf -resume
```

Select a profile:

```bash
nextflow run main.nf -profile workstation
```

---

## Input data

### Stage 01 — Repository CSVs (`input/stage01_scrap/`)

One CSV per repository host. Each row describes a dataset accessible via FTP.

| Column | Type | Required | Description |
|---|---|---|---|
| `doi` | string | yes | Publication DOI |
| `id` | string | yes | Repository accession (e.g. `PXD001064`, `MSV000094935`) |
| `url` | string | yes | FTP URL to the dataset root directory |

Example (`ftp.pride.ebi.ac.uk.csv`):

```csv
doi,id,url
10.1093/bioinformatics/btab284,PXD001064,ftp://ftp.pride.ebi.ac.uk/pride/data/archive/2015/01/PXD001064
10.1038/s41467-023-39869-5,PXD023325,ftp://ftp.jpostdb.org/JPST000971/
```

The `id` column must contain **unique** values — duplicates cause a pipeline error.

### Stage 02 — Batch annotation CSVs (`input/stage02_batch/`)

One CSV per accession (e.g. `PXD001064.csv`). Each row represents a replicate (sample run) with biological annotation.

| Column | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Replicate identifier (e.g. `PXD001064_yanliu_l130104_007_sw`) |
| `organism` | string | yes | Organism name (e.g. `human`, `mouse`) |
| `source_type` | string | yes | Source category (e.g. `clinical`, `cell_line`) |
| `material` | string | yes | Biological material (e.g. `plasma`, `liver`, `cells`) |
| `condition` | string | yes | Experimental condition (e.g. `healthy`, `treated`) |
| `sample_group` | string | yes | Grouping label for stratified splitting (e.g. `sample-0001`) |

Example (`PXD001064.csv`):

```csv
id,organism,source_type,material,condition,sample_group
PXD001064_yanliu_l130104_007_sw,human,clinical,plasma,healthy,sample-0001
```

Each file in this directory is validated against the `REPLICATES_SCHEMA` in `021_load_replicates.py`. The `id` column must be unique within each file.

### Stage 99 — Dump requests (`input/stage99_dumpdb/`)

Files with the `.request` extension. The pipeline uses the filename (without extension) as the output base name for the SQL dump and chart files. The file content is currently **not read** by the active scripts — the request serves as a trigger.

---

## Running the pipeline

### Basic execution

```bash
# Full pipeline (stages 01, 02, 99)
nextflow run main.nf

# Resume after interruption
nextflow run main.nf -resume
```

### Profiles

| Profile | queueSize | maxForks | Use case |
|---|---|---|---|
| `local` | 32 | (default) | Development / small runs |
| `workstation` | 64 | 32 | Desktop workstation |
| `server` | 128 | 64 | Dedicated server |
| `debug` | — | — | Verbose logging, no cleanup |

```bash
nextflow run main.nf -profile workstation
```

### Disabling stages

To skip the dump stage, comment out `DUMP()` in `main.nf`. To re-enable stages 03 or 04, uncomment their lines in `main.nf` — but note that their scripts are empty stubs and do not yet perform any work.

---

## Output structure

### `output/silver/` — Parquet tables (medallion silver layer)

| Subdirectory | Contents | Generated by |
|---|---|---|
| `repositories/` | One Parquet per repository (`repo_{id}.parquet`) | `REPOSITORY_TO_PARQUET` |
| `files/` | One Parquet per repository (`files_{id}.parquet`) with file inventory | `REPOSITORY_FILES_EXTRACT` |
| `replicates/` | One Parquet per accession — validated replicate annotations | `REPLICATES_TO_PARQUET` |
| `datasets/` | *(reserved)* | —
| `bronze_metadata/` | *(reserved)* | —

The `lib/silver_model.py` file documents the canonical schema for every silver table.

### `output/dump/01repo/` — Repository summary CSVs

For each repository two files are produced:

- **`samples_{id}.csv`** — Sample files (valid MS data, file size > 150 MiB) with placeholder annotation columns (`organism`, `source_type`, `material`, `condition`, `sample_group`) set to null, ready for manual completion.
- **`other_{id}.csv`** — Auxiliary files (small files, non-sample data, documentation).

### `output/dump/02batch/` — Stratified batch splits

CSV files named `{accession}_{split_id:03d}.csv`. Each split targets ~10 GB of total file size and preserves stratification by `organism`, `source_type`, `material`, and `condition`.

### `output/dump/99sqldump/` — SQL dumps and charts

- **`{request}.sql`** — SQL script with `CREATE TABLE` + `INSERT` statements for `repositories`, `files`, and `replicates` tables (from silver parquet data).
- **`{request}.repositories_by_replicates.png`** — Pie chart: replicate count per repository.
- **`{request}.repositories_by_size.png`** — Pie chart: storage footprint per repository.
- **`{request}.organism_by_replicates.png`** — Pie chart: replicate count per organism.
- **`{request}.organism_by_size.png`** — Pie chart: storage footprint per organism.
- **`{request}.{organism}.{column}.replicates.png`** — Per-organism breakdown by `source_type`, `material`, or `condition`.

---

## Workflow overview

The pipeline runs these stages in order:

```
01 REPOSITORY_SCRAP ──► 02 BATCH_SPLIT ──► [03 NORMALIZE] ──► [04 INGEST_BRONZE] ──► 99 DUMP
                                │                                                 ▲
                                ▼                                                 │
                         output/silver/                                    output/silver/
                         output/dump/01repo/                               output/dump/02batch/
```

- **Stages 01 and 02** are fully functional.
- **Stages 03 and 04** are commented out in `main.nf` and their Python scripts are empty stubs.
- **Stage 99** reads from `output/silver/` (generated by stages 01–02) so it must run after them.

See [WORKFLOWS.md](docs/WORKFLOWS.md) for detailed process-level documentation.

---

## Configuration

### `nextflow.config`

```nextflow
params {
    input_stage01 = 'input/stage01_scrap/*.csv'
    input_stage02 = 'input/stage02_batch/*.csv'
    input_stage03 = 'input/stage03_dataset/*.csv'
    input_dump    = 'input/stage99_dumpdb/*.request'
    silver_dir    = 'output/silver'
    bronze_dir    = 'output/bronze'
    dump_dir      = 'output/dump'
    silver_access = "${projectDir}/output/silver"
}

process {
    executor = 'local'
    shell    = ['/bin/bash', '-euo', 'pipefail']
}
```

### `nextflow-not.config`

An alternative configuration file that adds explicit `publishDir` directives per process. Use it by copying it over `nextflow.config` or by passing `-c nextflow-not.config`:

```bash
nextflow run main.nf -c nextflow-not.config
```

### Resource defaults (`conf/resources.config`)

| Process name | CPUs | Memory | Time |
|---|---|---|---|
| `REPOSITORY_TO_PARQUET` | 1 | 2 GB | 2 h |
| `REPOSITORY_FILES_EXTRACT` | 1 | 4 GB | 12 h |
| `REPOSITORY_SUMMARY` | 1 | 1 GB | 30 m |
| `REPLICATES_TO_PARQUET` | — | — | — |
| `BATCH_SPLIT_STRATIFIED` | 1 | 2 GB | 1 h |
| `DATASET_MANIFEST_TO_PARQUET` | 1 | 2 GB | 2 h |
| `DOWNLOAD_TRANSCODE_PUBLISH` | 1 | 8 GB | 48 h |
| `INGEST_BRONZE_METADATA` | 1 | 16 GB | 24 h |
| `PARQUET_TO_SQL_DUMP` | 1 | 4 GB | 4 h |
| `DUMP_BREAKDOWN` | — | — | — |

---

## Troubleshooting

| Problem | Likely cause | Solution |
|---|---|---|
| `uv: command not found` | uv is not installed | Install uv: `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `Failed to read CSV: ...` | Input CSV has missing columns or wrong format | Verify columns match the schemas documented in [Input data](#input-data). |
| `FTP scan failed after 3 attempts` | Repository FTP server unresponsive or network issue | Check network connectivity. The script retries with backoff. |
| `Silver mount not available` | Stage 02 runs before stage 01 completes | Run all stages together, or ensure `output/silver/files/` exists from a previous run. |
| `No parquet files found` | Stage 01 did not produce any file catalogs | Check the repository CSV URLs are correct and FTP servers are reachable. |
| `nextflow-not.config` not used | Default config is `nextflow.config` | Pass `-c nextflow-not.config` explicitly. |

---

## Development notes

- All Python scripts use the `#!/usr/bin/env -S uv run --with ... python3.12` shebang — dependencies are fetched automatically.
- The project uses **Nextflow DSL2** with workflows imported in `main.nf`.
- The `lib/silver_model.py` file is the single source of truth for Parquet schema definitions.
- The `modules/` directory contains **empty placeholder files** — processes are defined inline within the workflow files in `workflows/`.
- Stages 03 and 04 are scaffolded but not yet implemented. The scripts `031_batch_work_load.py`, `032_download_transcode_bronze.py`, and `041_ingest_bronze.py` are empty stubs.
- When adding a new process, follow the existing pattern: define the process inside the relevant `workflows/*.nf` file, write a Python script in `bin/`, and add resource defaults in `conf/resources.config`.
