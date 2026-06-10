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
        [--cores 4] \\
        [--backbone-from /data/runs/yfv-brazil/2023-06-01]

Exit codes:
    0 — success
    1 — pipeline error (see logs)
    2 — configuration / preflight error
"""

import argparse
import csv
import logging
import subprocess
import sys
from datetime import date
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


def validate_run_date(value: str) -> str:
    """Validate and normalize a ``YYYY-MM-DD`` run date."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"--run-date must be a valid YYYY-MM-DD date, got: {value}") from exc
    if parsed.isoformat() != value:
        raise SystemExit(f"--run-date must be in YYYY-MM-DD format, got: {value}")
    return value


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


def _seed_coordinate_cache(seed_cache: str | Path, paths: WorkdirPaths) -> None:
    """Copy the configured read-only seed cache to the workdir on first run."""
    _seed_coordinate_cache_with_shared(None, seed_cache, paths)


def _seed_coordinate_cache_with_shared(
    shared_cache: str | Path | None,
    seed_cache: str | Path | None,
    paths: WorkdirPaths,
) -> None:
    """Seed the workdir cache from bundled/shared and build-specific coordinate caches."""
    target = paths.cache_coordinates
    if target.exists():
        return
    from flexpipe.geo.cache import seed_coordinate_cache

    seed_coordinate_cache(
        shared_cache=shared_cache,
        build_cache=seed_cache,
        output_path=target,
    )


def _materialize_backbone(
    backbone_from: Path | None,
    paths: WorkdirPaths,
) -> Path | None:
    """Extract the previous run's subsampled strain list and write it to the workdir.

    Reads ``<backbone_from>/results/subsampled/metadata.tsv``, pulls the ``strain``
    column, and writes one strain per line to ``paths.backbone_strains``.  Returns the
    output path so the caller can set ``cfg.subsampling.backbone_strains``.

    Returns ``None`` (no-op) when:

    * *backbone_from* is ``None`` (feature disabled).
    * *backbone_from* resolves to the current workdir (self-reference guard — exits 2).
    * The previous metadata file is missing (warns, continues without backbone).
    * The previous metadata has no strains (warns, continues without backbone).

    Args:
        backbone_from: Path to the previous run's workdir, or ``None``.
        paths: :class:`~flexpipe.paths.WorkdirPaths` for the current run.

    Returns:
        Absolute :class:`~pathlib.Path` to the written include-list, or ``None``.
    """
    if backbone_from is None:
        return None

    prev_root = Path(backbone_from).resolve()
    if prev_root == paths.root:
        raise SystemExit(
            f"--backbone-from points at the current workdir ({paths.root}).\n"
            "Pass a *previous* run's workdir, not the one being built."
        )

    prev_metadata = WorkdirPaths.from_root(prev_root).subsampled_metadata
    if not prev_metadata.exists():
        logger.warning(
            "backbone: no subsampled metadata found at %s — proceeding without backbone.",
            prev_metadata,
        )
        return None

    strains: list[str] = []
    try:
        with open(prev_metadata, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            if reader.fieldnames is None or "strain" not in reader.fieldnames:
                logger.warning(
                    "backbone: previous metadata at %s has no 'strain' column — "
                    "proceeding without backbone.",
                    prev_metadata,
                )
                return None
            for row in reader:
                s = row.get("strain", "").strip()
                if s:
                    strains.append(s)
    except Exception as exc:
        logger.warning("backbone: could not read %s (%s) — proceeding without backbone.", prev_metadata, exc)
        return None

    if not strains:
        logger.warning(
            "backbone: previous metadata at %s contains no strains — proceeding without backbone.",
            prev_metadata,
        )
        return None

    out = paths.backbone_strains
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(strains) + "\n", encoding="utf-8")
    logger.info(
        "backbone: materialized %d strains from %s → %s",
        len(strains),
        prev_metadata,
        out,
    )
    return out


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
    backbone_from: Path | None = None,
) -> int:
    """Run the pipeline for one build.

    Args:
        config_path: Path to the build's ``config.yaml``.
        workdir: Output directory (all artifacts written here; source tree untouched).
        run_date: Reference date for this run (``YYYY-MM-DD``).
        stage: ``"ingest"``, ``"phylo"``, or ``"all"`` (default).
        cores: Number of CPU cores to pass to Snakemake.
        backbone_from: Path to a previous run's workdir.  When provided, the previous
            run's subsampled strain list is force-included in the new subsample so the
            sequence SET stays stable across reruns.  ``None`` (default) disables the
            feature — behaviour is identical to the current pipeline.

    Returns:
        Exit code (0 = success).
    """
    try:
        run_date = validate_run_date(run_date)
    except SystemExit as exc:
        logger.error("Configuration error: %s", exc)
        return 2

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
            backbone_from=backbone_from,
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
    backbone_from: Path | None = None,
) -> int:
    """Inner pipeline body — called inside the workdir lock."""
    # Materialize the backbone strain list before writing the resolved config so
    # cfg.subsampling.backbone_strains propagates into the single Snakemake --configfile.
    backbone_path = _materialize_backbone(backbone_from, paths)
    if backbone_path is not None:
        cfg.subsampling.backbone_strains = str(backbone_path)

    snakemake_overrides = write_snakemake_config_overrides(
        cfg, paths.snakemake_config_overrides, config_path
    )

    # Seed coordinate cache (read-only source → writable workdir)
    _seed_coordinate_cache_with_shared(cfg.coordinates.shared_cache, cfg.files.cache, paths)

    # Set up per-build log files
    configure_logging(
        log_file=paths.ingest_log if stage in ("ingest", "all") else paths.phylo_log,
        force=True,
    )

    manifest = Manifest(run_date=run_date, build_name=build_name, config_path=config_path)
    manifest.record_provenance(cfg, snakemake_overrides)
    if backbone_path is not None:
        manifest.record("backbone_from", str(backbone_from))
        manifest.record("backbone_strain_count", len(backbone_path.read_text().splitlines()))

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
            manifest.record_provenance(cfg, snakemake_overrides, paths.subsample_config_resolved)
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
            manifest.record_provenance(cfg, snakemake_overrides, paths.subsample_config_resolved)
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
    manifest.record_provenance(cfg, snakemake_overrides, paths.subsample_config_resolved)
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
        "--backbone-from",
        default=None,
        type=Path,
        metavar="PREV_WORKDIR",
        help=(
            "Path to a previous run's workdir.  When provided, the strain list from that "
            "run's results/subsampled/metadata.tsv is force-included in the new subsample "
            "via augur subsample's per-sample include mechanism.  The new subsample becomes "
            "the union of (stable backbone strains) + (freshly-selected new sequences), "
            "making results comparable across runs.  Omit for a fully-fresh subsample "
            "(default)."
        ),
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
        run_date = date.today().isoformat()
        logger.warning(
            "--run-date not provided; defaulting to today (%s). "
            "For scheduled/reproducible runs, always pass --run-date explicitly.",
            run_date,
        )
    else:
        run_date = validate_run_date(args.run_date)

    rc = run_pipeline(
        config_path=args.config.resolve(),
        workdir=args.workdir.resolve(),
        run_date=run_date,
        stage=args.stage,
        cores=args.cores,
        backbone_from=args.backbone_from.resolve() if args.backbone_from else None,
    )
    sys.exit(rc)
