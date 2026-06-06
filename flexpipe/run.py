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

import filelock

from flexpipe.config import FlexpipeConfig, load_config, write_snakemake_config_overrides
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


def _run_snakemake(
    snakefile: Path,
    config_path: Path,
    paths: WorkdirPaths,
    cores: int,
    config_overrides: Path | None = None,
    run_date: str = "",
) -> int:
    """Invoke Snakemake for one stage and return the exit code.

    Args:
        snakefile: Path to the Snakefile for this stage.
        config_path: Path to the build config.yaml (passed as ``build_config=`` so
            ``flexpipe-*`` CLI subprocesses can locate it).
        paths: WorkdirPaths for the current run.
        cores: Number of CPU cores to pass to Snakemake.
        config_overrides: Resolved config YAML written by
            ``write_snakemake_config_overrides``; used as the sole ``--configfile``.
        run_date: Reference date (``YYYY-MM-DD``) to pass as ``--config run_date=``.
            The ingest stage uses it to bound ``augur subsample`` via ``defaults.max_date``.
            Phylo ignores it but receives it for forward-compatibility.  Empty string
            means no date override (backwards-compatible for direct snakemake invocations).
    """
    cmd = [
        "snakemake",
        "--snakefile",
        str(snakefile),
        "--configfile",
        # Resolved config is the sole --configfile: it contains the full build config
        # merged with pydantic-resolved ViralQC paths.  Snakemake 9+ only loads the
        # last --configfile when multiple are passed, so a single complete file is
        # required.  Falls back to the raw build config for direct snakemake invocations.
        str(config_overrides) if config_overrides is not None else str(config_path),
    ]
    config_args = [
        f"workdir={paths.root}",
        f"build_config={config_path}",
    ]
    if run_date:
        config_args.append(f"run_date={run_date}")
    cmd.extend(["--config"] + config_args + ["--cores", str(cores), "--nolock"])
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
        cfg = load_config(config_path, workdir=workdir)
    except SystemExit as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    # Ensure workdir layout
    paths = WorkdirPaths.from_root(workdir)
    paths.ensure_dirs()

    # Acquire workdir-level lock to prevent concurrent runs on the same workdir.
    # Snakemake's native lock is scoped to the invocation directory (not the workdir),
    # so we manage the guard explicitly here.  timeout=0 → fail immediately if locked.
    lock = filelock.FileLock(str(paths.lock_file), timeout=0)
    try:
        lock.acquire()
    except filelock.Timeout:
        logger.error(
            "Another flexpipe-run process already holds the workdir lock: %s\n"
            "Wait for that run to finish, or remove the lock file manually: %s",
            workdir,
            paths.lock_file,
        )
        return 2

    try:
        return _run_pipeline_locked(
            cfg=cfg,
            config_path=config_path,
            build_dir=build_dir,
            build_name=build_name,
            paths=paths,
            run_date=run_date,
            stage=stage,
            cores=cores,
        )
    finally:
        lock.release()


def _run_pipeline_locked(
    cfg: FlexpipeConfig,
    config_path: Path,
    build_dir: Path,
    build_name: str,
    paths: WorkdirPaths,
    run_date: str,
    stage: str,
    cores: int,
) -> int:
    """Inner pipeline body — called inside the workdir lock."""
    snakemake_overrides = write_snakemake_config_overrides(
        cfg, paths.snakemake_config_overrides, config_path
    )

    # Seed coordinate cache (read-only source → writable workdir)
    _seed_coordinate_cache(build_dir, paths)

    # Set up per-build log files
    configure_logging(
        log_file=paths.ingest_log if stage in ("ingest", "all") else paths.phylo_log,
        force=True,
    )

    manifest = Manifest(run_date=run_date, build_name=build_name, config_path=config_path)

    min_sequences = cfg.qc.min_sequences

    rc = 0

    if stage in ("ingest", "all"):
        logger.info("=== Stage: ingest ===")
        rc = _run_snakemake(
            _INGEST_SNAKEFILE, config_path, paths, cores, snakemake_overrides, run_date=run_date
        )
        manifest.record("ingest_exit_code", rc)
        if rc != 0:
            logger.error("Ingest stage failed (exit code %d)", rc)
            manifest.record("status", "ingest_failed")
            manifest.save(paths.manifest)
            return rc
        _record_row_counts(manifest, paths)

    if stage in ("phylo", "all"):
        # Boundary check before phylogenetics: column contract + min-sequences guardrail.
        # Run for both "all" and standalone "phylo" so the guardrail always applies.
        try:
            manifest.validate_boundary(paths.subsampled_metadata, min_sequences=min_sequences)
        except SystemExit as exc:
            logger.error("Boundary check failed: %s", exc)
            manifest.record("status", "boundary_failed")
            manifest.save(paths.manifest)
            return 1
        logger.info("=== Stage: phylogenetic ===")
        rc = _run_snakemake(
            _PHYLO_SNAKEFILE, config_path, paths, cores, snakemake_overrides, run_date=run_date
        )
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
