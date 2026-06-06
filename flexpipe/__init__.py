"""
flexpipe — Flexible Nextstrain pipeline for genomic epidemiology of viral pathogens.

Supports data ingestion from Pathoplexus, NCBI, or local surveillance sequences;
automated quality control via ViralQC (BLAST + Nextclade); and a complete
phylogenetic workflow producing Auspice-compatible JSON for visualization.

Designed to run as an automated service: parameterized by (config, workdir, run-date),
never mutates the source tree, and emits structured logs and run provenance manifests.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("flexpipe")
except PackageNotFoundError:
    # Package is not installed (e.g. running directly from source without pip install)
    __version__ = "0.0.0+unknown"
