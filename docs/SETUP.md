# Setup and Environment Preparation

This document covers prerequisites, K3s configuration for single-node use, container images, and storage for running nf_octaprot with the Nextflow Kubernetes executor.

## Prerequisites (verified)
From `nextflow.config`/scripts:
- **Nextflow**: `>= 24.04.0` (manifest). Install from https://www.nextflow.io/.
- **Java**: Required by Nextflow. Version depends on Nextflow; check with `java -version`.
- **Docker**: For building images. Note: Docker daemon and K3s containerd do **not** share the image store.
- **K3s**: Lightweight Kubernetes for single-node/local testing.
- **kubectl**: To manage cluster/namespace/pods (recommended).
- **uv**: Python package/dependency manager (used by all `bin/*.py` via shebang). Install from https://docs.astral.sh/uv/.
- **Python**: 3.12 referenced in some shebangs; `uv` will manage environments.
- **Network**: Access to public FTP (PRIDE/jPOST) for stages 1 and 3.

**Check with**: `./setup.sh` (see end of this doc).

## Nextflow and Java
```bash
# Java
java -version

# Nextflow
curl -s https://get.nextflow.io | bash
chmod +x nextflow
sudo mv nextflow /usr/local/bin/  # or add to PATH
nextflow -version
```

## K3s Setup (single-node)
K3s is recommended for local testing. The following settings are common; **verify against your cluster**.

### Suggested installation/config
A fragment sometimes used:
```yaml
write-kubeconfig-mode: "0644"
disable:
  - traefik
```
- **`write-kubeconfig-mode: "0644"`**: Makes `/etc/rancher/k3s/k3s.yaml` readable by all local users. Convenient for local dev, but **widens access** (any local user can read cluster admin credentials). For shared machines use more restrictive permissions and manage via groups/sudo.
- **`disable: - traefik`**: Disables Traefik ingress controller. **Not obviously required** by this pipeline — Nextflow K8s executor talks to API server to create pods; no ingress is configured in repo. Only disable if Traefik conflicts with your setup or you don't need it.

Install (example):
```bash
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644 --disable traefik
```
Or configure via `/etc/rancher/k3s/config.yaml` and restart k3s.

### Verify cluster
```bash
# Check node
kubectl get nodes
# Should show Ready

# Check context/namespace
kubectl config current-context
kubectl get ns

# Check system pods
kubectl get pods -A
```

### Kubeconfig access
- If installed with `--write-kubeconfig-mode 644`, kubeconfig is at `/etc/rancher/k3s/k3s.yaml`. You may need to set `KUBECONFIG` or copy to `~/.kube/config` with appropriate permissions.
- More securely: use `sudo cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config && chmod 600 ~/.kube/config` and adjust server address if needed.
- Ensure your user can access the cluster; `kubectl auth can-i create pods` helps.

### Namespace and permissions
Nextflow config sets `k8s.namespace = 'nextflow'` and mounts hostPath `/home`. You need a namespace and RBAC allowing Nextflow to create/delete pods, configmaps, etc. For a single-node dev cluster, you can create namespace and give admin to a service account, or use cluster-admin for testing only.
```bash
kubectl create namespace nextflow
# Create/service account as needed; verify with kubectl auth can-i
```
**Note**: `kubectl` success does not guarantee Nextflow executor works — Nextflow uses its own API calls with configured context/namespace/service account.

### Single-node limitations
- **CPU/memory contention**: All pods share node resources; large processes (transcode 8CPU/16GB, search up to 128GB) may queue/Pending.
- **Local storage**: Host paths/PVCs limited by disk; ensure space for `work/`, `output/`, downloads.
- **Pod scheduling**: Taints/tolerations not configured; single node means no HA.
- **Node failure**: No redundancy.
- **Network**: FTP access from pods depends on network policies/firewall.

## Container Images
### Images used (from processes)
| Process | Image | Notes |
|---------|-------|-------|
| default process | `dev.ilab.usm.cl/dia/nf_octaprot_uv_base` | set in `nextflow.config` process.container |
| transcode | `dev.ilab.usm.cl/dia/nf_octaprot_transcode` | Wine + msconvert (`lib/Dockerfile_032_download_transcode_bronze`) |
| alphadia | `dev.ilab.usm.cl/dia/nf_octaprot_alphadia` | `lib/Dockerfile_alphadia` |
| diann | `dev.ilab.usm.cl/dia/nf_octaprot_diann` | `lib/Dockerfile_diann` (v2.5.1) |
| msfragger | `dev.ilab.usm.cl/dia/nf_octaprot_msfragger` | `lib/Dockerfile_msfragger` (needs MSFragger JAR in `MSFragger/`) |
| sage | `dev.ilab.usm.cl/dia/nf_octaprot_sage` | `lib/Dockerfile_sage` |
| uv base | built from `lib/Dockerfile_uv` context | used as base for uv |

Dockerfiles in `lib/`:
- `Dockerfile_uv`: `python:3.12-slim-bookworm` + uv + procps
- `Dockerfile_032_download_transcode_bronze`: uv + proteowizard base + tools
- `Dockerfile_diann`: ubuntu22.04 + DIA-NN 2.5.1 + dotnet-sdk-8.0 + time
- `Dockerfile_msfragger`: needs local `MSFragger/MSFragger-*.jar` and `ext/` (COPY in Dockerfile) — ensure present before build
- `Dockerfile_alphadia`: clones repo in build, installs deps
- `Dockerfile_sage`: from `ghcr.io/lazear/sage:latest` + time

### Building images
Build from repo root with appropriate context. Tag to match process image names.
```bash
# Example builds (adjust tags to match your registry/cluster)
docker build -f lib/Dockerfile_uv -t dev.ilab.usm.cl/dia/nf_octaprot_uv_base .
docker build -f lib/Dockerfile_032_download_transcode_bronze -t dev.ilab.usm.cl/dia/nf_octaprot_transcode .
docker build -f lib/Dockerfile_diann -t dev.ilab.usm.cl/dia/nf_octaprot_diann .
# MSFragger needs JARs present
docker build -f lib/Dockerfile_msfragger -t dev.ilab.usm.cl/dia/nf_octaprot_msfragger .
docker build -f lib/Dockerfile_alphadia -t dev.ilab.usm.cl/dia/nf_octaprot_alphadia .
docker build -f lib/Dockerfile_sage -t dev.ilab.usm.cl/dia/nf_octaprot_sage .
```
Verify: `docker images | grep nf_octaprot`

### Making images available to K3s
**Docker and K3s do not share image store.** Options:
1. **Import to K3s containerd** (single-node): save/load or use `k3s ctr images import`. For example:
```bash
docker save dev.ilab.usm.cl/dia/nf_octaprot_uv_base | sudo k3s ctr images import -
# repeat for other images
```
Or use `ctr` from k3s. Alternatively build directly in environment accessible to containerd.
2. **Use a local registry**: run registry accessible to cluster, push images, set `imagePullPolicy: IfNotPresent` or appropriate.
3. **Use `imagePullPolicy`**: In Nextflow K8s, you can set per-process; default behavior may try to pull. If image only in Docker daemon, pods will fail with `ErrImagePull`/`ImagePullBackOff`. Set `imagePullPolicy = 'IfNotPresent'` if using imported images, or ensure registry is configured.

**Verify**: `sudo k3s ctr images list | grep nf_octaprot`

## Storage and Input Files
### How files are accessed
- **Nextflow config** (`nextflow.config`): `k8s.pod` mounts hostPath `/home` to `/home` in pods; `autoMountHostPaths = false`. Also sets `workDir = "${projectDir}/work"`. Processes use containers; scripts read from paths under project dir (params like `${projectDir}/input/...`, `${projectDir}/output/...`).
- **Work directory**: `work/` is used by Nextflow for task execution/caching (important for `-resume`).
- **Outputs**: Published via `publishDir`/`storeDir` to `output/silver`, `output/bronze`, `output/dump`, `output/gold` as configured.
- **Input**: Must be placed in `input/stage01_scrap/`, `input/stage02_batch/`, etc. With hostPath mount to `/home`, paths depend on where project lives; ensure pods can access same paths.

### Single-node practical config
For single-node K3s with hostPath mounts:
- Ensure project is under a path accessible (e.g., `/home/...`) and mounted via k8s.pod hostPath or adjust config.
- Set appropriate directory permissions so pods can read inputs and write outputs/work.
- Use local disk with enough space.

### PVCs/shared storage
Current config uses **hostPath mount to `/home`** (not PVCs). If you need persistence across node restarts or different scheduling, consider PVCs, but current implementation expects host paths. Changing this may require modifying `nextflow.config`.

### Directory permissions
```bash
chmod -R u+rwX input output work logs
```
Ensure the user running Nextflow/kubectl and pod user context can access mounted paths.

## Python/uv preparation
Scripts use `uv run` with inline deps. No global pip install required. Ensure `uv` is in PATH for the environment running Nextflow (and available in containers if needed). The `lib/Dockerfile_uv` installs uv; base images may need uv depending on how processes are configured.

## Quick verification
```bash
./setup.sh
java -version && nextflow -version && docker version && kubectl version --client && k3s --version 2>&1 | head -1
```
