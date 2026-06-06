#!/usr/bin/env bash
# install_viralqc.sh — set up the bundled viralQC submodule for flexpipe
#
# Usage:
#   bash scripts/install_viralqc.sh [OPTIONS]
#
# Options:
#   --cores N           Threads for dataset downloads (default: 2)
#   --env-name NAME     Conda environment name (default: viralQC, taken from env.yml)
#   --skip-datasets     Skip Nextclade + BLAST database download
#   --skip-tests        Skip viralQC post-install test suite
#   -h, --help          Show this message
#
# After a successful run flexpipe auto-discovers viralQC/datasets so no
# manual VIRALQC_DATASETS_DIR export or config.yaml edit is needed.

set -euo pipefail

# ─── Defaults ────────────────────────────────────────────────────────────────
CORES=2
ENV_NAME="viralQC"
SKIP_DATASETS=false
SKIP_TESTS=false

# ─── Parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cores)       CORES="$2";     shift 2 ;;
        --env-name)    ENV_NAME="$2";  shift 2 ;;
        --skip-datasets) SKIP_DATASETS=true; shift ;;
        --skip-tests)    SKIP_TESTS=true;    shift ;;
        -h|--help)
            sed -n '/^# Usage:/,/^[^#]/p' "$0" | head -n -1 | sed 's/^# \?//'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# ─── Locate repo root (script lives in <repo>/scripts/) ──────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SUBMODULE_DIR="$REPO_ROOT/viralQC"

echo "=== flexpipe: ViralQC install script ==="
echo "Repo root  : $REPO_ROOT"
echo "Submodule  : $SUBMODULE_DIR"
echo "Env name   : $ENV_NAME"
echo "Cores      : $CORES"
echo ""

# ─── 1. Ensure submodule is checked out ──────────────────────────────────────
if [[ ! -f "$SUBMODULE_DIR/env.yml" ]]; then
    echo ">> Submodule not initialised — running: git submodule update --init --recursive"
    git -C "$REPO_ROOT" submodule update --init --recursive
fi

if [[ ! -f "$SUBMODULE_DIR/env.yml" ]]; then
    echo "ERROR: viralQC/env.yml still missing after submodule init." >&2
    exit 1
fi
echo ">> Submodule OK: $SUBMODULE_DIR"

# ─── 2. Detect environment manager ───────────────────────────────────────────
MGR=""
for candidate in micromamba mamba conda; do
    if command -v "$candidate" &>/dev/null; then
        MGR="$candidate"
        break
    fi
done

if [[ -z "$MGR" ]]; then
    echo "" >&2
    echo "ERROR: No conda-compatible environment manager found on PATH." >&2
    echo "Please install one of: micromamba, mamba, or conda." >&2
    echo "  micromamba: https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html" >&2
    echo "  miniforge (includes mamba+conda): https://github.com/conda-forge/miniforge" >&2
    exit 1
fi
echo ">> Using environment manager: $MGR"

# ─── 3. Create the viralQC conda environment (idempotent) ────────────────────
# Extract the env name from env.yml (name: ... field), using our --env-name as override.
ENV_FROM_YML=$(grep '^name:' "$SUBMODULE_DIR/env.yml" 2>/dev/null | head -1 | awk '{print $2}' || true)
if [[ -z "$ENV_NAME" && -n "$ENV_FROM_YML" ]]; then
    ENV_NAME="$ENV_FROM_YML"
fi

# Check if the env already exists by listing environments
ENV_EXISTS=false
if "$MGR" env list 2>/dev/null | grep -qE "^$ENV_NAME[[:space:]]|/$ENV_NAME$|/$ENV_NAME "; then
    ENV_EXISTS=true
fi

if $ENV_EXISTS; then
    echo ">> Conda env '$ENV_NAME' already exists — skipping creation."
else
    echo ">> Creating conda env '$ENV_NAME' from $SUBMODULE_DIR/env.yml ..."
    "$MGR" env create -f "$SUBMODULE_DIR/env.yml" -n "$ENV_NAME"
    echo ">> Conda env '$ENV_NAME' created."
fi

# ─── 4. Install viralQC into the env (editable) ──────────────────────────────
echo ">> Installing viralQC (pip install -e) into env '$ENV_NAME' ..."
"$MGR" run -n "$ENV_NAME" pip install -e "$SUBMODULE_DIR[dev]" --quiet
echo ">> viralQC installed."

# Quick smoke check
"$MGR" run -n "$ENV_NAME" vqc --help > /dev/null
echo ">> vqc --help OK."

# ─── 5. Download datasets (Nextclade + BLAST) ────────────────────────────────
DATASETS_DIR="$SUBMODULE_DIR/datasets"

if $SKIP_DATASETS; then
    echo ">> --skip-datasets: skipping dataset download."
else
    echo ""
    echo ">> Downloading Nextclade datasets (this may take a few minutes) ..."
    # vqc downloads to a 'datasets/' dir relative to CWD; run from the submodule dir
    (cd "$SUBMODULE_DIR" && "$MGR" run -n "$ENV_NAME" vqc get-nextclade-datasets --cores "$CORES")

    echo ">> Downloading BLAST database (this may take 10-30+ minutes) ..."
    (cd "$SUBMODULE_DIR" && "$MGR" run -n "$ENV_NAME" vqc get-blast-database --cores "$CORES")

    # Verify expected output files
    if [[ ! -f "$DATASETS_DIR/blast.fasta" ]]; then
        echo "ERROR: BLAST database not found after download: $DATASETS_DIR/blast.fasta" >&2
        exit 1
    fi
    if [[ ! -f "$DATASETS_DIR/blast.tsv" ]]; then
        echo "ERROR: BLAST database metadata not found after download: $DATASETS_DIR/blast.tsv" >&2
        exit 1
    fi
    echo ">> Datasets OK: $DATASETS_DIR"
fi

# ─── 6. Run viralQC tests ─────────────────────────────────────────────────────
if $SKIP_TESTS; then
    echo ">> --skip-tests: skipping post-install test suite."
else
    if [[ -d "$SUBMODULE_DIR/tests" ]]; then
        echo ""
        echo ">> Running viralQC test suite ..."
        (cd "$SUBMODULE_DIR" && "$MGR" run -n "$ENV_NAME" pytest tests/ -v)
        echo ">> viralQC tests passed."
    else
        echo ">> No tests/ directory found in submodule — skipping."
    fi
fi

# ─── 7. Warn if conda is absent (Snakefile uses 'conda run') ─────────────────
if [[ "$MGR" != "conda" ]] && ! command -v conda &>/dev/null; then
    echo ""
    echo "WARNING: The flexpipe ingest/Snakefile uses 'conda run -n $ENV_NAME vqc ...'." >&2
    echo "         'conda' was not found on PATH (you used '$MGR')." >&2
    echo "         Either install conda/miniforge, or set 'viralqc.conda_env' in" >&2
    echo "         builds/yfv-brazil/config.yaml to an env accessible by '$MGR run'." >&2
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Install complete ==="
echo ""
echo "  Datasets  : $DATASETS_DIR"
echo "  Conda env : $ENV_NAME"
echo ""
echo "flexpipe will auto-discover datasets from viralQC/datasets — no further"
echo "configuration needed. You can override with:"
echo "  export VIRALQC_DATASETS_DIR=/custom/path   (shell)"
echo "  viralqc.datasets_dir: /custom/path         (config.yaml)"
