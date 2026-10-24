# nf_octaprot — Proteomics Repository Aggregation and Analysis Pipeline

nf_octaprot is a Nextflow DSL2 pipeline for discovering proteomics datasets from public FTP repositories (PRIDE, jPOST), building file inventories, preparing annotated replicate batches, downloading/transcoding raw data to mzML.gz, running peptide search with multiple engines, and producing silver/gold Parquet outputs.

## Overview

- **Stage 1 (Repository scraping)**: `nextflow run main.nf --stage stage1` will scrap records  in `input/stage01_scrap/*.csv` for samples (required for full traceability)
- **Stage 2 (Replicate/batch preparation)**: `nextflow run main.nf --stage stage2` will download, convert to mzML labeled samples from `input/stage02_batch/*.csv`
- **Stage 3 (Search/processing)**: `nextflow run main.nf --stage stage2` will do peptide search on samples against database `input/stage00_fasta/*.fasta`

## Prerequisites

### Required minimum
- **Nextflow (DSL2)**: Orchestrator. Default executor is **Kubernetes (`k8s`)**.
- **Kubernetes/K3s**: Target execution backend; K3s is suitable for single-node local processing.

### Optional
- **Docker**: Required to build Dockerfiles are present in `lib/Dockerfile_*` locally.
- **uv**: To manually run scripts in `bin/*.py`.
- **DuckDB**: To query parquet silver storage.

## Quick Start
1. **Install unnecessary Prerequisites**: A working nexflow with K3s is bare minimum.
2. **Prepare input data**: Put CSVs in appropriate `input/stage*/` dirs (current dataset is from `assets/*.zip`).
5. **Execute workflow**: `nextflow run main.nf --stage stage1` (and then stage2/stage3).
6. **Inspect results**: Check `output/silver/`, `output/bronze/`, `output/dump/`.

## Installation

### Prerequisites

- **Linux** or **macOS** (not tested).
- **Java 17 or later**: Required by Nextflow.
- **Nextflow**: Version `24.04.0` or later.
- **K3s**: Lightweight Kubernetes for local, single-node testing.
- **Docker**: Required to build container images.
- **uv**: Python package and dependency manager.
- **Disk space**: Approximately 500 GB free for the current dataset.
- **Network access**: Required to download data from public FTP servers (PRIDE, jPOST, MassIVE).

### Java

Check your Java version:

```bash
java -version
```

Install Java 17 on Ubuntu/Debian:

```bash
sudo apt update && sudo apt install openjdk-17-jre
```

On macOS, using Homebrew:

```bash
brew install openjdk@17
```

### Nextflow

Install Nextflow 24.04.0 or later:

```bash
curl -s https://get.nextflow.io | bash
chmod +x nextflow
sudo mv nextflow /usr/local/bin/
nextflow -version
```

### uv (Python package manager)

All Python scripts use `uv` in their shebang to automatically resolve dependencies. Install it using the standalone installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

Python dependencies are defined in the headers of the individual scripts and are managed by `uv`.

### K3s (single-node Kubernetes)

K3s is recommended for local testing with the Nextflow Kubernetes executor.

Install K3s:

```bash
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644 --disable traefik
```

Alternatively, configure `/etc/rancher/k3s/config.yaml`:

```yaml
write-kubeconfig-mode: "0644"
disable:
  - traefik
```

Restart K3s after changing the configuration.

Configure kubeconfig access:

```bash
mkdir -p ~/.kube
sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config
chmod 600 ~/.kube/config
```

Ensure your user can access the cluster and create pods:

```bash
kubectl get nodes
kubectl config current-context
kubectl get ns
kubectl get pods -A
kubectl auth can-i create pods
```

The node should report `Ready`.

### Kubernetes namespace and permissions

Nextflow is configured to use the `nextflow` namespace and mount the host path `/home`. Create the namespace:

```bash
kubectl create namespace nextflow
```

Ensure the Kubernetes identity used by Nextflow has permission to create and delete pods and manage the required ConfigMaps. Configure the appropriate service account and RBAC permissions for your cluster. Cluster-admin permissions should be used for testing only.

Note that successful `kubectl` commands do not guarantee that the Nextflow Kubernetes executor is configured correctly. Nextflow uses its configured Kubernetes context, namespace, and service account.

### Container images

**Note:** Although you can build the images, k3s can't read them from docker, so it will download them from the configure registry. TODO: allow customize registry to store images locally.

The pipeline uses the following container images:

| Process | Image | Dockerfile |
|---|---|---|
| Default (uv) | `dev.ilab.usm.cl/dia/nf_octaprot_uv_base` | `Dockerfile_uv` |
| Transcode | `dev.ilab.usm.cl/dia/nf_octaprot_transcode` | `Dockerfile_032_download_transcode_bronze` |
| AlphaDIA | `dev.ilab.usm.cl/dia/nf_octaprot_alphadia` | `Dockerfile_alphadia` |
| DIA-NN | `dev.ilab.usm.cl/dia/nf_octaprot_diann` | `Dockerfile_diann` |
| MSFragger | `dev.ilab.usm.cl/dia/nf_octaprot_msfragger` | `Dockerfile_msfragger` |
| Sage | `dev.ilab.usm.cl/dia/nf_octaprot_sage` | `Dockerfile_sage` |

Build the images from the `lib` directory:

```bash
cd lib

docker build -f Dockerfile_uv -t dev.ilab.usm.cl/dia/nf_octaprot_uv_base .
docker build -f Dockerfile_032_download_transcode_bronze -t dev.ilab.usm.cl/dia/nf_octaprot_transcode .
docker build -f Dockerfile_alphadia -t dev.ilab.usm.cl/dia/nf_octaprot_alphadia .
docker build -f Dockerfile_diann -t dev.ilab.usm.cl/dia/nf_octaprot_diann .
docker build -f Dockerfile_msfragger -t dev.ilab.usm.cl/dia/nf_octaprot_msfragger .
docker build -f Dockerfile_sage -t dev.ilab.usm.cl/dia/nf_octaprot_sage .
```

**Note:** MSFragger requires manually downloading the MSFragger JAR file into the `MSFragger/` directory before building its image.

Verify the images:

```bash
docker images | grep nf_octaprot
```

### Verify the installation

Test that Nextflow can parse the pipeline:

```bash
nextflow run main.nf -stub-run
```

Test a Python script:

```bash
./bin/011_repository_to_parquet.py
```

Check the Kubernetes cluster:

```bash
kubectl get nodes
kubectl get pods -n nextflow
```


## Repository Structure
Key directories/files (verified):
- `main.nf`, `nextflow.config`, `nextflow-not.config` (local executor variant), `conf/profiles.config`, `conf/resources.config`
- `workflows/` - stage workflows; `modules/` - process definitions
- `bin/*.py` - all pipeline scripts (uv-based)
- `lib/` - Dockerfiles (`lib/Dockerfile_*`), schemas (`silver_model.py`, SQL generators)
- `input/`, `output/` - input/output dirs
- `assets/` - sample input zips
- `docs/` - documentation

## Workflow Execution

This document describes actual workflow stages, how to launch with the Kubernetes executor, monitoring, resumption, and troubleshooting.

### Workflow stages
From `main.nf` and workflows/modules:

| Stage | Workflow | Purpose | Status |
|-------|----------|---------|--------|
| `stage1` | `WORKFLOW_REPOSITORY` | Scrap repositories from `input/stage01_scrap/*.csv`, inventory files via FTP, produce silver files + summary CSVs for annotation | Active |
| `stage2` | `WORKFLOW_REPLICATES` | Load annotated replicates from `input/stage02_batch/*.csv`, stratify/split batches using file sizes from silver | Active (part of WORKFLOW_REPLICATES; also does download/search in full workflow but main routes by stage) |
| `stage3` | `WORKFLOW_SEARCH` | Download/transcode to bronze, run peptide searches (MSFragger/DIANN/SAGE/AlphaDIA), save PSMs/runtimes to silver | Active |



#### Stage 1: Repository scraping
**Inputs**: `input/stage01_scrap/*.csv` (schema: `doi,id,url` per scripts)
**Run**: `nextflow run main.nf --stage stage1 -resume`

#### Stage 2: Sample preparation
**Inputs**: `input/stage02_batch/*.csv` (schema requires `replicate_id,organism,source_type,material,condition,sample_group` per previous stage output `output/dump/01repo/*.csv` )
**Run**: `nextflow run main.nf --stage stage2 -resume`

#### Stage 3: Peptide Search
**Inputs**: FASTA from `input/stage00_fasta/*.fasta`. TODO: add some Analysis after is done.
**Run**: `nextflow run main.nf --stage stage3 -resume`

### Launch commands
All run from repo root on the host:
```bash
# Stage 1
nextflow run main.nf --stage stage1 -resume

# Stage 2 (after stage1)
nextflow run main.nf --stage stage2 -resume

# Stage 3 (after stage2 and having FASTA inputs)
nextflow run main.nf --stage stage3 -resume
```

### Monitoring
```bash
# Nextflow logs
tail -f .nextflow.log

# Kubernetes pods
kubectl get pods -n nextflow -w
kubectl describe pod <pod> -n nextflow
kubectl logs <pod> -n nextflow
```

## Output and DuckDB usage (Silver or Gold)

From config and processes:
- `output/bronze/` - mzML.gz files from transcode
- `output/silver/` - Parquet tables produced by pipeline (raw metadate in SQL format)
- `output/gold/` - gold Parquet Tables of curated data for fast queries
- `output/dump/` - summary CSVs/SQL/PNGs (`01repo/`, `02batch/`, `99sqldump/`, `097_GoldReport/`)


### Is parquet partitioned?

Inside every folder there is individual parquet files, they are generated independently by the pipepine, but they can be merged together into a single database table as they share schema. Most tables (directories) contain a file per sample, being the name of the file its unique id. That can help of optimize large queries by filtering the files being queried to avoid unnecessary computation.


### DuckDB usage example on silver
#### Read a single Parquet file
```sql
SELECT * FROM read_parquet('output/silver/sample_metadata/PXD001064.parquet') LIMIT 5;
```

#### Read a Parquet dataset (directory of files)
```sql
-- Read all repositories
SELECT * FROM read_parquet('output/silver/repositories/*.parquet');

-- Read all files
SELECT * FROM read_parquet('output/silver/files/*.parquet');

-- Read all replicates
SELECT * FROM read_parquet('output/silver/replicates/*.parquet');
```

#### Inspect schema
```sql
DESCRIBE SELECT * FROM read_parquet('output/silver/replicates/*.parquet');
-- or
SELECT * FROM parquet_schema('output/silver/replicates/*.parquet');
```

#### Count rows
```sql
SELECT COUNT(*) AS cnt FROM read_parquet('output/silver/files/*.parquet');
SELECT COUNT(*) AS cnt FROM read_parquet('output/silver/replicates/*.parquet');
```

#### Select a few records
```sql
SELECT replicate_id, organism, material, condition
FROM read_parquet('output/silver/replicates/*.parquet')
LIMIT 10;
```

#### Filter records
```sql
SELECT replicate_id, remote_path, size_bytes
FROM read_parquet('output/silver/files/*.parquet')
WHERE replicate_id IS NOT NULL
LIMIT 20;
```

#### Aggregate by relevant column
```sql
SELECT organism, COUNT(*) AS n_replicates, SUM(size_bytes)/1e9 AS total_gb
FROM read_parquet('output/silver/files/*.parquet') f
JOIN read_parquet('output/silver/replicates/*.parquet') r
  ON f.replicate_id = r.replicate_id
WHERE f.replicate_id IS NOT NULL
GROUP BY organism
ORDER BY total_gb DESC;
```
