# ── Base image ────────────────────────────────────────────────────────────────
# Pinned to a specific dated tag for reproducibility.
# Update policy: bump this tag when upgrading the nextstrain conda environment.
# Check https://hub.docker.com/r/condaforge/miniforge3/tags for the latest
# dated release that matches `latest`, then update the tag and re-build.
#
# Current: 26.3.2-3 (matches `latest` as of 2026-06-03)
FROM condaforge/miniforge3:26.3.2-3

WORKDIR /app

# ── Install conda environment ─────────────────────────────────────────────────
# Uses the pinned lock file (config/nextstrain.lock.yml) to ensure reproducible
# tool versions across runs.  For a flexible/dev install, replace with
# config/nextstrain.yml.
COPY config/nextstrain.lock.yml /tmp/nextstrain.yml
RUN conda env create -f /tmp/nextstrain.yml && \
    conda clean -afy

# ── Copy source and install the package ──────────────────────────────────────
# .dockerignore ensures .git/, viralQC/, tests/, and builds/ are excluded.
# Because .git/ is absent, hatch-vcs cannot derive the version from git tags.
# SETUPTOOLS_SCM_PRETEND_VERSION tells it to use the declared version instead.
ARG FLEXPIPE_VERSION=0.2.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${FLEXPIPE_VERSION}

COPY . /app
RUN conda run -n nextstrain pip install --no-deps -e .

# ── Runtime notes ─────────────────────────────────────────────────────────────
# ViralQC datasets are NOT included in this image (multi-GB).
# Mount them at runtime via VIRALQC_DATASETS_DIR:
#
#   docker run --rm \
#     -v /path/to/viralqc/datasets:/datasets \
#     -e VIRALQC_DATASETS_DIR=/datasets \
#     -v /path/to/builds:/builds \
#     -v /path/to/workdir:/workdir \
#     flexpipe flexpipe-run \
#       --config /builds/yfv-brazil/config.yaml \
#       --workdir /workdir/yfv-brazil \
#       --run-date 2026-01-01

# Default entrypoint runs flexpipe-run inside the nextstrain env.
# Override CMD to pass --config and --workdir at runtime.
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "nextstrain"]
CMD ["flexpipe-run", "--help"]
