"""
Orchestrator — runs both Snakemake stages end-to-end for one build.

This is the scheduler's entry point: a single ``flexpipe-run`` command that:
1. Validates config and ViralQC preflight
2. Ensures the workdir layout
3. Seeds the coordinate cache from the build's read-only seed (if not yet seeded)
4. Runs the ingest Snakemake stage
5. Validates the ingest→phylo boundary (column contract check)
6. Runs the phylogenetic Snakemake stage
7. Writes a run manifest (counts, tool versions, provenance)

Usage::

    flexpipe-run \\
        --config builds/yfv-brazil/config.yaml \\
        --workdir /data/runs/yfv-brazil/2025-06-01 \\
        --run-date 2025-06-01 \\
        [--stage ingest|phylo|all] \\
        [--cores 4]

Exit codes:
    0 — success
    1 — pipeline error (see logs)
    2 — configuration / preflight error
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from flexpipe.config import load_config
from flexpipe.logging_setup import configure_logging
from flexpipe.manifest import Manifest
from flexpipe.paths import WorkdirPaths

logger = logging.getLogger(__name__)

# Snakefile paths relative to the repository root (resolved at import time)
_REPO_ROOT = Path(__file__).parent.parent
_INGEST_SNAKEFILE = _REPO_ROOT / "ingest" / "Snakefile"
_PHYLO_SNAKEFILE = _REPO_ROOT / "phylogenetic" / "Snakefile"


def _record_row_counts(manifest: Manifest, paths: WorkdirPaths) -> None:
    """Read row counts from ingest outputs and record them in the manifest."""
    candidates = [
        ("merged", paths.ingest_dir / "merged_metadata.tsv"),
        ("curated", paths.ingest_dir / "final_metadata.tsv"),
        ("subsampled", paths.subsampled_metadata),
    ]
    for stage, tsv_path in candidates:
        if tsv_path.exists():
            try:
                count = sum(1 for _ in open(tsv_path)) - 1  # exclude header
                manifest.record_counts(stage, max(count, 0))
            except Exception:
                pass


def _seed_coordinate_cache(build_dir: Path, paths: WorkdirPaths) -> None:
    """Copy the read-only seed cache from the build directory to the workdir on first run."""
    seed = build_dir / "cache_coordinates.tsv"
    target = paths.cache_coordinates
    if not target.exists() and seed.exists():
        import shutil

        shutil.copy2(seed, target)
        logger.info("Seeded coordinate cache from %s → %s", seed, target)


def _run_snakemake(snakefile: Path, config_path: Path, paths: WorkdirPaths, cores: int) -> int:
    """Invoke Snakemake for one stage and return the exit code."""
    cmd = [
        "snakemake",
        "--snakefile",
        str(snakefile),
        "--configfile",
        str(config_path),
        "--config",
        f"workdir={paths.root}",
        "--cores",
        str(cores),
        "--nolock",
    ]
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    return result.returncode


def run_pipeline(
    config_path: Path,
    workdir: Path,
    run_date: str,
    stage: str = "all",
    cores: int = 4,
) -> int:
    """Run the pipeline for one build.

    Args:
        config_path: Path to the build's ``config.yaml``.
        workdir: Output directory (all artifacts written here; source tree untouched).
        run_date: Reference date for this run (``YYYY-MM-DD``).
        stage: ``"ingest"``, ``"phylo"``, or ``"all"`` (default).
        cores: Number of CPU cores to pass to Snakemake.

    Returns:
        Exit code (0 = success).
    """
    build_dir = config_path.parent
    build_name = build_dir.name

    # Load and validate config
    try:
        load_config(config_path, workdir=workdir)
    except SystemExit as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    # Ensure workdir layout
    paths = WorkdirPaths.from_root(workdir)
    paths.ensure_dirs()

    # Seed coordinate cache (read-only source → writable workdir)
    _seed_coordinate_cache(build_dir, paths)

    # Set up per-build log files
    configure_logging(
        log_file=paths.ingest_log if stage in ("ingest", "all") else paths.phylo_log,
        force=True,
    )

    manifest = Manifest(run_date=run_date, build_name=build_name, config_path=config_path)

    rc = 0

    if stage in ("ingest", "all"):
        logger.info("=== Stage: ingest ===")
        rc = _run_snakemake(_INGEST_SNAKEFILE, config_path, paths, cores)
        manifest.record("ingest_exit_code", rc)
        if rc != 0:
            logger.error("Ingest stage failed (exit code %d)", rc)
            manifest.record("status", "ingest_failed")
            manifest.save(paths.manifest)
            return rc
        _record_row_counts(manifest, paths)

    if stage in ("phylo", "all"):
        # Boundary check before phylogenetics
        if stage == "all":
            try:
                manifest.validate_boundary(paths.subsampled_metadata)
            except SystemExit as exc:
                logger.error("Boundary check failed: %s", exc)
                manifest.record("status", "boundary_failed")
                manifest.save(paths.manifest)
                return 1
        logger.info("=== Stage: phylogenetic ===")
        rc = _run_snakemake(_PHYLO_SNAKEFILE, config_path, paths, cores)
        manifest.record("phylo_exit_code", rc)
        if rc != 0:
            logger.error("Phylogenetic stage failed (exit code %d)", rc)
            manifest.record("status", "phylo_failed")
        else:
            manifest.record("status", "success")

    if stage == "ingest" and rc == 0:
        manifest.record("status", "success")

    manifest.record("stage", stage)
    manifest.record("cores", cores)
    manifest.save(paths.manifest)
    logger.info("Pipeline finished (exit code %d)", rc)
    return rc


def main() -> None:
    """Entry point for ``flexpipe-run``."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the flexpipe pipeline for one build end-to-end.\n\n"
            "Both the ingest and phylogenetic stages are run in sequence. "
            "All output is written to --workdir; the source tree is never modified."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the build config.yaml (e.g. builds/yfv-brazil/config.yaml)",
    )
    parser.add_argument(
        "--workdir",
        required=True,
        type=Path,
        help="Output directory for all artifacts (created if it does not exist)",
    )
    parser.add_argument(
        "--run-date",
        default=None,
        help="Reference date for this run (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--stage",
        choices=["ingest", "phylo", "all"],
        default="all",
        help="Pipeline stage to run (default: all)",
    )
    parser.add_argument(
        "--cores",
        type=int,
        default=4,
        help="Number of CPU cores for Snakemake (default: 4)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    configure_logging(level=args.log_level)

    # Resolve run_date: must be explicit for reproducibility; warn if defaulting to today
    if args.run_date is None:
        from datetime import date

        run_date = date.today().isoformat()
        logger.warning(
            "--run-date not provided; defaulting to today (%s). "
            "For scheduled/reproducible runs, always pass --run-date explicitly.",
            run_date,
        )
    else:
        run_date = args.run_date

    rc = run_pipeline(
        config_path=args.config.resolve(),
        workdir=args.workdir.resolve(),
        run_date=run_date,
        stage=args.stage,
        cores=args.cores,
    )
    sys.exit(rc)
