#!/usr/bin/env bash
# setup.sh - Prerequisite and environment diagnostics for nf_octaprot
# Safe to run; does not modify system/cluster or launch workflow

set -u
set -o pipefail

# Resolve repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT" || exit 1

PASS=0
WARN=0
FAIL=0
INFO_COUNT=0

log_pass() { echo -e "[PASS] $1"; PASS=$((PASS+1)); }
log_warn() { echo -e "[WARN] $1"; WARN=$((WARN+1)); }
log_fail() { echo -e "[FAIL] $1"; FAIL=$((FAIL+1)); }
log_info() { echo -e "[INFO] $1"; INFO_COUNT=$((INFO_COUNT+1)); }

echo "=== nf_octaprot Environment Diagnostics ==="
echo "Repo root: $REPO_ROOT"
echo "Date: $(date)"
echo "User: $(whoami)"
echo

# OS
log_info "OS: $(uname -s) $(uname -m)"
if [ -f /etc/os-release ]; then
    . /etc/os-release
    log_info "Distribution: ${NAME:-unknown} ${VERSION:-}"
fi

# Required files
echo "--- Required files ---"
for f in nextflow.config main.nf bin workflows modules lib; do
    if [ -e "$f" ]; then
        log_pass "Present: $f"
    else
        log_fail "Missing: $f"
    fi
done

# Commands
echo
echo "--- Commands in PATH ---"
check_cmd() {
    local cmd="$1"
    local required="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        local ver
        ver=$($cmd --version 2>&1 | head -1)
        log_pass "$cmd found: $ver"
        return 0
    else
        if [ "$required" = "required" ]; then
            log_fail "$cmd not found in PATH"
        else
            log_warn "$cmd not found in PATH (optional/depends)"
        fi
        return 1
    fi
}

check_cmd java required
check_cmd nextflow required
check_cmd docker required
check_cmd kubectl required
check_cmd k3s required  # may not be in PATH if installed differently
check_cmd uv required
check_cmd python3 optional
check_cmd git optional

# Java version details
if command -v java >/dev/null 2>&1; then
    JV=$(java -version 2>&1 | head -1)
    log_info "Java: $JV"
fi

# Nextflow version
if command -v nextflow >/dev/null 2>&1; then
    NFV=$(nextflow -version 2>&1 | head -2 | tr '\n' ' ')
    log_info "Nextflow: $NFV"
fi

# Docker daemon
echo
echo "--- Docker daemon ---"
if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        log_pass "Docker daemon reachable"
    else
        log_fail "Docker daemon not reachable (is it running?)"
    fi
fi

# K3s service
echo
echo "--- K3s/service ---"
if systemctl is-active --quiet k3s 2>/dev/null; then
    log_pass "k3s service is active"
elif systemctl is-active --quiet k3s-agent 2>/dev/null; then
    log_pass "k3s-agent service is active"
else
    log_warn "k3s/k3s-agent systemd service not active or not found"
fi

# kubectl context/namespace
echo
echo "--- Kubernetes ---"
if command -v kubectl >/dev/null 2>&1; then
    if CTX=$(kubectl config current-context 2>/dev/null); then
        log_pass "kubectl context: $CTX"
    else
        log_fail "Cannot get kubectl context"
    fi
    NS=$(kubectl config view --minify --output 'jsonpath={..namespace}' 2>/dev/null)
    [ -z "$NS" ] && NS="(default/not set)"
    log_info "Current namespace: $NS"
    if kubectl get nodes >/dev/null 2>&1; then
        NODES=$(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}:{.status.conditions[?(@.type=="Ready")].status} ' 2>/dev/null)
        log_pass "Cluster reachable. Nodes: $NODES"
    else
        log_fail "Cannot reach cluster with kubectl"
    fi
    # check namespace from config
    if grep -q "namespace = 'nextflow'" nextflow.config 2>/dev/null; then
        if kubectl get namespace nextflow >/dev/null 2>&1; then
            log_pass "Namespace 'nextflow' exists"
        else
            log_warn "Namespace 'nextflow' not found (create with: kubectl create namespace nextflow)"
        fi
    fi
fi

# uv/python
echo
echo "--- Python/uv ---"
if command -v uv >/dev/null 2>&1; then
    UVV=$(uv --version 2>&1)
    log_pass "uv: $UVV"
fi
if command -v python3 >/dev/null 2>&1; then
    PYV=$(python3 --version 2>&1)
    log_info "python3: $PYV"
fi

# Input/output dirs
echo
echo "--- Project dirs ---"
for d in input output work logs; do
    if [ -d "$d" ]; then
        if [ -w "$d" ]; then
            log_pass "Writable dir: $d"
        else
            log_warn "Not writable: $d"
        fi
    else
        log_fail "Missing dir: $d"
    fi
done

# Input subdirs
for sd in input/stage01_scrap input/stage02_batch input/stage03_dataset input/stage99_dumpdb; do
    if [ -d "$sd" ]; then
        cnt=$(find "$sd" -type f ! -name ".gitignore" | wc -l)
        log_info "$sd has $cnt non-gitignore files"
    fi
done

# Container images (local/docker)
echo
echo "--- Container images ---"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    imgs="dev.ilab.usm.cl/dia/nf_octaprot_uv_base dev.ilab.usm.cl/dia/nf_octaprot_transcode dev.ilab.usm.cl/dia/nf_octaprot_diann dev.ilab.usm.cl/dia/nf_octaprot_msfragger dev.ilab.usm.cl/dia/nf_octaprot_sage dev.ilab.usm.cl/dia/nf_octaprot_alphadia"
    for img in $imgs; do
        if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^$img$"; then
            log_pass "Docker image exists: $img"
        else
            log_warn "Docker image missing: $img (build/import needed)"
        fi
    done
fi

# K3s containerd images
if command -v k3s >/dev/null 2>&1 || [ -f /usr/local/bin/k3s ]; then
    if sudo -n k3s ctr images list >/dev/null 2>&1; then
        log_info "k3s containerd accessible (check images with: sudo k3s ctr images list | grep nf_octaprot)"
    else
        log_warn "Cannot access k3s containerd without sudo (check images with: sudo k3s ctr images list)"
    fi
fi

# Summary
echo
echo "=== Summary ==="
echo "PASS: $PASS  WARN: $WARN  FAIL: $FAIL"
if [ $FAIL -gt 0 ]; then
    echo "Status: NOT READY - fix FAIL items"
    exit 1
else
    echo "Status: OK (check WARN items)"
    exit 0
fi
