# Workflow Execution

This document describes actual workflow stages, how to launch with the Kubernetes executor, monitoring, resumption, and troubleshooting.

## Workflow stages (verified)
From `main.nf` and workflows/modules:

| Stage | Workflow | Purpose | Status |
|-------|----------|---------|--------|
| `stage1` | `WORKFLOW_REPOSITORY` | Scrap repositories from `input/stage01_scrap/*.csv`, inventory files via FTP, produce silver files + summary CSVs for annotation | Active |
| `stage2` | `WORKFLOW_REPLICATES` | Load annotated replicates from `input/stage02_batch/*.csv`, stratify/split batches using file sizes from silver | Active (part of WORKFLOW_REPLICATES; also does download/search in full workflow but main routes by stage) |
| `stage3` | `WORKFLOW_SEARCH` | Download/transcode to bronze, run peptide searches (MSFragger/DIANN/SAGE/AlphaDIA), save PSMs/runtimes to silver | Active |

Notes:
- `workflows/02replicate.nf` contains a more complete pipeline (download/transcode, metadata extraction, gold) but `main.nf` routes stage2 to `WORKFLOW_REPLICATES()` as defined there; inspect actual flow as needed.
- `workflows/03search.nf` reads from `output/silver/replicates/*.parquet` and `output/bronze/*.mzML.gz`.
- Stages 4 (`INGEST_BRONZE`) and 99 (`DUMP`) exist but are not routed by `main.nf` currently.

## Stage details

### Stage 1: Repository scraping
**Inputs**: `input/stage01_scrap/*.csv` (schema: `doi,id,url` per scripts)
**Processes**:
- `REPOSITORY_TO_PARQUET` (`bin/011_repository_to_parquet.py`): validates schema, rejects nulls/empties/dupes, writes one parquet per repo to `output/silver/repositories/*.parquet`
- `REPOSITORY_FILES_EXTRACT` (`bin/012_repository_scrap.py`): FTP scan (handles TLS for massive-ftp, retries), fuses `.wiff.scan`, marks large sample files (>150MiB, known extensions) with generated `replicate_id` as `{repo_id}_{sample_base}`, writes to `output/silver/files/{repo_id}.parquet`
- `REPOSITORY_SUMMARY` (`bin/013_repository_summary_csv.py`): splits files into samples (replicate_id not null) and others, writes to `output/dump/01repo/`

**Run**: `nextflow run main.nf --stage stage1 -resume`

### Stage 2: Replicates/batches
**Inputs**: `input/stage02_batch/*.csv` (schema requires `replicate_id,organism,source_type,material,condition,sample_group` per `021_load_replicates.py`)
**Processes**:
- `LOAD_REPLICATES` (`bin/021_load_replicates.py`): validates and writes to `output/silver/replicates/*.parquet`
- `BATCH_SPLIT_STRATIFIED` (`bin/022_batch_split.py`): reads `output/silver/files/*.parquet` via `SILVER_DIR`, joins on `replicate_id`, stratifies by `organism,source_type,material,condition`, shuffles (seed 42), bin-packs to ~10GB splits, writes to `output/dump/02batch/`

**Run**: `nextflow run main.nf --stage stage2 -resume` (after stage1/populating silver/files)

### Stage 3: Search
**Inputs**: FASTA from `params.input_fasta` (`${projectDir}/input/stage00_fasta/*.fasta`), replicates from `output/silver/replicates/*.parquet`, bronze files from `output/bronze/*.mzML.gz`
**Flow**:
- Lists DIA/DDA replicates via `031_get_replicates.py` based on acquisition metadata
- `DOWNLOAD_TRANSCODE_PUBLISH` downloads raw files and transcodes with msconvert (Wine) to `output/bronze/{id}.mzML.gz`
- For each engine (MSFragger/DIANN/SAGE/AlphaDIA) runs config/search, saves PSMs via `032_save_psm.py` to `output/silver/psm/{engine}/`, runtimes via `033_save_time.py` to `output/silver/psm_runtime/{engine}/`

**Run**: `nextflow run main.nf --stage stage3 -resume`

## Kubernetes executor configuration
From `nextflow.config`:
```groovy
process {
    executor = 'k8s'
    cpus = 1
    memory = '2 GB'
    container = 'dev.ilab.usm.cl/dia/nf_octaprot_uv_base'
    errorStrategy = 'ignore'
}
k8s {
    namespace = 'nextflow'
    pod = [[ hostPath: '/home', mountPath: '/home' ]]
    autoMountHostPaths = false
}
```
- Executor is **Kubernetes** by default.
- Namespace: `nextflow` (create if missing).
- HostPath mount `/home` -> `/home` for all pods.
- `autoMountHostPaths = false`.
- Resources can be overridden per process in `conf/resources.config` and modules.

**Select profile**: `nextflow.config` does not show `includeConfig` of profiles by default; `conf/profiles.config` defines `local/workstation/server/debug` (local executor). To use profiles: `-profile workstation` etc., but they set `executor = 'local'` — do **not** treat as equivalent to K8s.

## Launch commands
All run from repo root on the host:
```bash
# Check
./setup.sh

# Stage 1
nextflow run main.nf --stage stage1 -resume

# Stage 2 (after stage1)
nextflow run main.nf --stage stage2 -resume

# Stage 3 (after stage2 and having FASTA inputs)
nextflow run main.nf --stage stage3 -resume
```

## Monitoring
```bash
# Nextflow logs
tail -f .nextflow.log

# Kubernetes pods
kubectl get pods -n nextflow -w
kubectl describe pod <pod> -n nextflow
kubectl logs <pod> -n nextflow
```

## Resume
Use `-resume`. Nextflow uses `work/` cache; successful tasks are reused. If inputs/params change, cache may be invalidated.

## Common errors and troubleshooting
| Issue | Cause | Resolution |
|-------|-------|------------|
| `ImagePullBackOff`/`ErrImagePull` | Images not in K3s containerd/registry | Import images to K3s (`k3s ctr images import`) or push to accessible registry; set `imagePullPolicy` appropriately |
| Pods Pending | Resources/taints/storage | Check `kubectl describe pod`, node resources, PVCs/hostPath permissions |
| Permission denied writing | HostPath permissions | `chmod -R u+rwX` on mounted paths; check pod user/context |
| FTP failures | Network/firewall/auth | Stage 1/3 need FTP access; scripts retry (stage1 up to 3x) |
| Java/Nextflow version | Incompatible | Use Nextflow >=24.04.0, compatible Java |
| Missing inputs | Wrong paths/empty dirs | Ensure CSVs in correct `input/stage*/`, follow naming |
| Empty/wrong outputs | Schema validation failed | Check script errors in logs/pod logs |

For detailed diagnostics, use `./setup.sh` and inspect pod logs.
