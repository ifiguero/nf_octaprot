# Workflows

This document describes every workflow and process in the pipeline, how they connect, and what data flows between them.

---

## Execution order

```
main.nf
  ├── REPOSITORY_SCRAP   (01repository_scrap.nf) — functional
  ├── BATCH_SPLIT        (02batch_split.nf)       — functional
  ├── [NORMALIZE]        (03normalize.nf)         — DISABLED
  ├── [INGEST_BRONZE]    (04ingest_bronze.nf)     — DISABLED
  └── DUMP               (99dump.nf)              — functional
```

Stages run sequentially in the order listed in `main.nf`. Stages 03 and 04 are commented out.

---

## Workflow: `REPOSITORY_SCRAP` (stage 01)

**File:** `workflows/01repository_scrap.nf`

**Purpose:** Read a list of proteomics repositories from CSV, validate them, connect to each via FTP, and build a file inventory.

### Data flow

```
stage01_scrap/*.csv
       │
       ▼
REPOSITORY_TO_PARQUET ──► output/silver/repositories/repo_{id}.parquet
       │
       ▼
REPOSITORY_FILES_EXTRACT ──► output/silver/files/files_{id}.parquet
       │
       ▼
REPOSITORY_SUMMARY ──► output/dump/01repo/samples_{id}.csv
                   └──► output/dump/01repo/other_{id}.csv
```

### Process: `REPOSITORY_TO_PARQUET`

- **Script:** `bin/011_repository_to_parquet.py`
- **Input:** A CSV file from `input/stage01_scrap/`
- **Output:** One Parquet file per repository row: `repo_{id}.parquet`
- **Validation:**
  - Requires columns: `doi`, `id`, `url`
  - Rejects nulls, empty strings, duplicate rows, and duplicate `id` values
  - Output is one row per Parquet file (one file per repository)
- **Resource default:** 1 CPU, 2 GB RAM, 2 h timeout

### Process: `REPOSITORY_FILES_EXTRACT`

- **Script:** `bin/012_repository_scrap.py`
- **Input:** A single-row Parquet file from `REPOSITORY_TO_PARQUET`
- **Output:** `files_{id}.parquet` — all files and directories found at the FTP URL
- **Behaviour:**
  - Connects via FTP (supports TLS for MassIVE, plain FTP for PRIDE/jPOST)
  - Recursively scans directories; `.d` directories (Bruker) are treated as single entries
  - `.wiff.scan` files are fused with their parent `.wiff` file sizes
  - Files > 150 MiB with recognized sample extensions (`.raw`, `.d`, `.mgf`, `.mzml`, `.wiff`, `.wiff2`) get a generated sample `id`; smaller/non-sample files get `id = null`
  - Retries up to 3 times with exponential backoff
- **Resource default:** 1 CPU, 4 GB RAM, 12 h timeout (single-threaded: `maxForks 1`)

### Process: `REPOSITORY_SUMMARY`

- **Script:** `bin/013_repository_summary_csv.py`
- **Input:** A Parquet file from `REPOSITORY_FILES_EXTRACT`
- **Output:** Two CSV files per repository:
  - `samples_{id}.csv` — Rows where `id` is not null (valid sample files). Includes placeholder columns (`organism`, `source_type`, `material`, `condition`, `sample_group`) set to null and an auto-generated `sample_group` label. These CSVs are intended for **manual annotation** — users fill in the biological metadata.
  - `other_{id}.csv` — Rows where `id` is null (auxiliary files: documentation, methods files, etc.)
- **Resource default:** 1 CPU, 1 GB RAM, 30 m timeout

---

## Workflow: `BATCH_SPLIT` (stage 02)

**File:** `workflows/02batch_split.nf`

**Purpose:** Convert annotated replicate CSVs into Parquet, join with file sizes from silver, and split into size-balanced stratified batches.

### Data flow

```
stage02_batch/*.csv
       │
       ▼
REPLICATES_TO_PARQUET ──► output/silver/replicates/{id}.parquet
       │
       ▼
BATCH_SPLIT_STRATIFIED ──► output/dump/02batch/{accession}_{split_id:03d}.csv
                         (reads: output/silver/files/*.parquet for size data)
```

### Process: `REPLICATES_TO_PARQUET`

- **Script:** `bin/021_load_replicates.py`
- **Input:** A CSV file from `input/stage02_batch/` (one per accession)
- **Output:** A Parquet file written alongside the input CSV (same basename, `.parquet` extension)
- **Validation:**
  - Requires columns: `id`, `organism`, `source_type`, `material`, `condition`, `sample_group`
  - All six columns are non-nullable
  - Rejects nulls, empty strings, and duplicate `id` values
- **Resource default:** Not specified (inherits process defaults)

### Process: `BATCH_SPLIT_STRATIFIED`

- **Script:** `bin/022_batch_split.py`
- **Input:** A Parquet file from `REPLICATES_TO_PARQUET`
- **Reads additionally:** `output/silver/files/*.parquet` (via `SILVER_DIR` environment variable) to obtain `size_bytes` for each replicate
- **Output:** Multiple CSV files named `{accession}_{split_id:03d}.csv`
- **Behaviour:**
  - Joins replicates with file sizes on `id` (inner join — skips replicates without size info)
  - Stratifies by `organism`, `source_type`, `material`, `condition`
  - Within each stratum, shuffles (seed 42) and sorts by size descending
  - Assigns rows to splits using a greedy bin-packing algorithm targeting 10 GB per split
- **Resource default:** 1 CPU, 2 GB RAM, 1 h timeout

---

## Workflow: `NORMALIZE` (stage 03) — DISABLED

**File:** `workflows/03normalize.nf`

**Status:** Commented out in `main.nf`. Scripts are empty stubs.

### Processes (scaffolded only)

| Process | Script | Status |
|---|---|---|
| `DATASET_MANIFEST_TO_PARQUET` | `bin/031_batch_work_load.py` | Empty file |
| `DOWNLOAD_TRANSCODE_PUBLISH` | `bin/032_download_transcode_bronze.py` | Empty file |

**Intended purpose** (inferred from workflow structure, `nextflow-not.config`, and schema definitions):
- Read dataset manifest CSVs from `input/stage03_dataset/`
- Download raw data files from remote repositories
- Transcode them to a standard format (`.mzML.gz`)
- Publish to `output/bronze/`

---

## Workflow: `INGEST_BRONZE` (stage 04) — DISABLED

**File:** `workflows/04ingest_bronze.nf`

**Status:** Commented out in `main.nf`. The script is an empty stub.

| Process | Script | Status |
|---|---|---|
| `INGEST_BRONZE_METADATA` | `bin/041_ingest_bronze.py` | Empty file |

**Intended purpose** (inferred from schema definitions in `lib/silver_model.py`):
- Read bronze files from `output/bronze/`
- Extract metadata (row count, column count, format, checksum, etc.)
- Write profiling statistics to `output/silver/bronze_metadata/` as Parquet

---

## Workflow: `DUMP` (stage 99)

**File:** `workflows/99dump.nf`

**Purpose:** Export silver-layer parquet data to a portable SQL script and generate summary visualisations.

### Data flow

```
stage99_dumpdb/*.request
       │
       ├──► PARQUET_TO_SQL_DUMP ──► output/dump/99sqldump/{request}.sql
       │
       └──► DUMP_BREAKDOWN ──► output/dump/99sqldump/{request}.*.png
                              (reads: output/silver/*.parquet)
```

### Process: `PARQUET_TO_SQL_DUMP`

- **Script:** `bin/991_parquet_to_sql_dump.py`
- **Input:** A `.request` file from `input/stage99_dumpdb/`
- **Output:** `{request_name}.sql` — a SQL script wrapped in `BEGIN` / `COMMIT`
- **Behaviour:**
  - Reads the request filename (content is not parsed — the file serves only as a trigger)
  - Reads Parquet files from `output/silver/repositories/`, `output/silver/files/`, and `output/silver/replicates/`
  - Generates `CREATE TABLE IF NOT EXISTS` statements for `repositories`, `files`, and `replicates`
  - Generates `INSERT INTO` statements for every row
  - SQL types are mapped: `string → TEXT`, `int64 → BIGINT`, `timestamp → TIMESTAMP`, etc.
- **Resource default:** 1 CPU, 4 GB RAM, 4 h timeout

### Process: `DUMP_BREAKDOWN`

- **Script:** `bin/992_dump_breakdown.py`
- **Input:** A `.request` file from `input/stage99_dumpdb/`
- **Output:** Multiple PNG pie charts in `output/dump/99sqldump/`
- **Behaviour:**
  - Joins `replicates` with `files` on `id` to get per-replicate organism/size data
  - Generates global charts:
    - Replicate count by repository
    - Storage size by repository
    - Replicate count by organism
    - Storage size by organism
  - Generates per-organism OLAP charts breaking down by `source_type`, `material`, and `condition`
  - Small groups (< 2% of total) are aggregated into an "Other" slice
  - Charts are 600 DPI, single-column publication format
- **Resource default:** Not specified (inherits process defaults)

---

## Silver-layer schema reference

The canonical schemas are defined in `lib/silver_model.py`. Every Parquet file in `output/silver/` conforms to one of these schemas.

### `repositories`

| Column | Type | Nullable |
|---|---|---|
| `id` | string | no |
| `url` | string | no |
| `doi` | string | no |

### `files`

| Column | Type | Nullable |
|---|---|---|
| `id` | string | yes |
| `repository_id` | string | no |
| `remote_path` | string | no |
| `size_bytes` | int64 | yes |
| `scan_timestamp` | timestamp | yes |

### `replicates`

| Column | Type | Nullable |
|---|---|---|
| `id` | string | no |
| `organism` | string | no |
| `source_type` | string | no |
| `material` | string | no |
| `condition` | string | no |
| `sample_group` | string | no |
