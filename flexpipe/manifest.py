"""
Run manifest — provenance record written at the ingest→phylo boundary and run end.

The manifest captures:
- ``run_id``: unique identifier for this run (config hash + run_date)
- ``run_date``: the reference date used for this analysis window
- ``build``: build name (from config) and data source + organism
- ``counts``: record counts at each pipeline stage (fetched, merged, curated, subsampled)
- ``config_hash``: SHA-256 of the merged config YAML (reproducibility check)
- ``tool_versions``: augur, iqtree, mafft, vqc package versions
- ``flexpipe_version``: ``flexpipe.__version__``

The manifest also performs a **boundary schema check**: before the phylogenetic stage
starts, it asserts that ``results/subsampled/metadata.tsv`` contains the minimum
expected columns, failing fast with a clear message rather than a late augur error.

Usage::

    from flexpipe.manifest import Manifest
    m = Manifest(run_date="2025-06-01", build_name="yfv-brazil")
    m.record_counts("fetched", 1469)
    m.record_counts("subsampled", 342)
    m.validate_boundary(subsampled_metadata_path)
    m.save(workdir_paths.manifest)
"""

import hashlib
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from flexpipe import __version__

logger = logging.getLogger(__name__)
_VERSION_CACHE: dict[tuple[str, ...], str] = {}

# Minimum columns that must be present in subsampled metadata before phylogenetics starts.
# This is the ingest→phylo boundary contract.
BOUNDARY_REQUIRED_COLUMNS = {
    "strain",
    "date",
    "country",
    "division",
    "location",
    "clade",
    "clade_truncated",
    "region",
    "source",
    "data_use",
}


def _run_version(cmd: list) -> str:
    """Run a command and return its version string, or 'unknown' on failure."""
    key = tuple(cmd)
    if key in _VERSION_CACHE:
        return _VERSION_CACHE[key]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        version = result.stdout.strip() or result.stderr.strip() or "unknown"
    except Exception:
        version = "unknown"
    _VERSION_CACHE[key] = version
    return version


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _git_state() -> dict[str, object]:
    repo = _repo_root()
    commit = _run_version(["git", "-C", str(repo), "rev-parse", "HEAD"]).splitlines()[0]
    status = _run_version(["git", "-C", str(repo), "status", "--short"])
    return {
        "commit": commit,
        "dirty": bool(status and status != "unknown"),
    }


def _file_digest(path: Union[str, Path], *, max_hash_bytes: int = 50_000_000) -> dict[str, object]:
    p = Path(path)
    info: dict[str, object] = {"path": str(p)}
    if not p.exists():
        info["exists"] = False
        return info
    stat = p.stat()
    info.update({"exists": True, "size": stat.st_size, "mtime": int(stat.st_mtime)})
    if p.is_file() and stat.st_size <= max_hash_bytes:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        info["sha256"] = h.hexdigest()
    elif p.is_file():
        info["sha256"] = "skipped_large_file"
    return info


def _directory_fingerprint(path: Union[str, Path]) -> dict[str, object]:
    p = Path(path)
    info: dict[str, object] = {"path": str(p), "exists": p.exists()}
    if not p.exists() or not p.is_dir():
        return info
    count = 0
    total_size = 0
    latest_mtime = 0
    metadata_hash = hashlib.sha256()
    for root, _, files in os.walk(p):
        for filename in sorted(files):
            file_path = Path(root) / filename
            try:
                stat = file_path.stat()
            except OSError:
                continue
            rel = str(file_path.relative_to(p))
            count += 1
            total_size += stat.st_size
            latest_mtime = max(latest_mtime, int(stat.st_mtime))
            metadata_hash.update(f"{rel}\t{stat.st_size}\t{int(stat.st_mtime)}\n".encode())
    info.update(
        {
            "file_count": count,
            "total_size": total_size,
            "latest_mtime": latest_mtime,
            "metadata_sha256": metadata_hash.hexdigest(),
        }
    )
    return info


def _hash_config(config_path: Union[str, Path], run_date: Optional[str] = None) -> str:
    """Return a short SHA-256 digest covering config.yaml, adjacent build files, and run_date.

    Including *run_date* in the digest ensures that two runs of the same build config on
    different reference dates produce different ``config_hash`` values and therefore
    different ``run_id``\\s — reflecting the distinct analysis windows.

    Args:
        config_path: Path to the build ``config.yaml``.
        run_date: Reference date (``YYYY-MM-DD``) to bind the analysis window, or ``None``.
    """
    try:
        config_path = Path(config_path)
        build_dir = config_path.parent
        h = hashlib.sha256()
        # Always include the config file itself (may be named config.yaml or otherwise)
        h.update(config_path.read_bytes())
        # Include other deterministic build inputs if present
        for name in sorted(
            ["subsample.yaml", "clades.tsv", "reference.gb", "masks/reference_terminal.bed"]
        ):
            candidate = build_dir / name
            if candidate.exists():
                h.update(candidate.read_bytes())
        # Bind the analysis window so different run_dates yield different hashes
        if run_date:
            h.update(run_date.encode())
        return h.hexdigest()[:16]
    except Exception:
        return "unknown"


class Manifest:
    """Accumulates run provenance and writes a manifest.json.

    Args:
        run_date: The reference date for this run (``YYYY-MM-DD``).
        build_name: Human-readable build identifier (e.g. ``"yfv-brazil"``).
        config_path: Path to the build config file (used to compute config hash).
    """

    def __init__(
        self,
        run_date: str,
        build_name: str,
        config_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.run_date = run_date
        self.build_name = build_name
        self.config_hash = _hash_config(config_path, run_date) if config_path else "unknown"
        self.counts: dict[str, int] = {}
        self.extra: dict[str, object] = {}
        self._start_time: float = time.time()

    @property
    def run_id(self) -> str:
        """Stable identifier: build + date + config hash."""
        return f"{self.build_name}/{self.run_date}/{self.config_hash}"

    def record_counts(self, stage: str, count: int) -> None:
        """Record the number of records at a named pipeline stage."""
        self.counts[stage] = count
        logger.info("Stage '%s': %d records", stage, count)

    def record(self, key: str, value) -> None:
        """Record an arbitrary key/value pair in the manifest."""
        self.extra[key] = value

    def collect_tool_versions(self) -> dict[str, str]:
        """Attempt to collect versions of external tools."""
        return {
            "flexpipe": __version__,
            "snakemake": _run_version(["snakemake", "--version"]),
            "augur": _run_version(["augur", "--version"]),
            "iqtree": _run_version(["iqtree3", "--version"]),
            "mafft": _run_version(["mafft", "--version"]),
            "viralqc": _run_version(["vqc", "--version"]),
        }

    def record_provenance(
        self,
        cfg,
        resolved_config: Union[str, Path],
        resolved_subsample: Union[str, Path] | None = None,
    ) -> None:
        """Record resolved config/input fingerprints for auditability."""
        inputs = {}
        for section_name, section in [
            ("files", cfg.files),
            ("local_sequences", cfg.local_sequences),
        ]:
            for key, value in section.model_dump().items():
                if value and isinstance(value, str):
                    path = Path(value)
                    if path.exists() and path.is_file():
                        inputs[f"{section_name}.{key}"] = _file_digest(path)

        resolved = {"config": _file_digest(resolved_config)}
        if resolved_subsample and Path(resolved_subsample).exists():
            resolved["subsample_config"] = _file_digest(resolved_subsample)

        self.record("resolved_config_digest", resolved["config"].get("sha256", "unknown"))
        self.record("resolved_inputs", inputs)
        self.record("resolved_artifacts", resolved)
        self.record("git", _git_state())
        self.record(
            "viralqc",
            {
                "runner": getattr(cfg.viralqc, "runner", "conda"),
                "executable": getattr(cfg.viralqc, "executable", "vqc"),
                "conda_env": getattr(cfg.viralqc, "conda_env", "viralQC"),
                "datasets": _directory_fingerprint(getattr(cfg.viralqc, "datasets_dir", "")),
            },
        )

    def validate_boundary(
        self,
        subsampled_metadata: Union[str, Path],
        min_sequences: int = 0,
    ) -> None:
        """Assert the ingest→phylo column contract and minimum-sequences guardrail.

        Reads *subsampled_metadata* and verifies:
        1. Every column in ``BOUNDARY_REQUIRED_COLUMNS`` is present.
        2. When *min_sequences* > 0, the file contains at least that many data rows.
           Timetree inference is unreliable on very small datasets; this check prevents
           a silent but meaningless phylogeny from being produced.

        Raises ``SystemExit`` with a clear message on failure so Snakemake surfaces it
        cleanly.  Passing ``min_sequences=0`` (the default) skips the row-count check,
        preserving backward-compatibility for callers that do not configure the guardrail.

        Args:
            subsampled_metadata: Path to ``results/subsampled/metadata.tsv``.
            min_sequences: Minimum number of sequences required to proceed.
                ``0`` disables the check.
        """
        path = Path(subsampled_metadata)
        if not path.exists():
            raise SystemExit(
                f"Boundary check failed: subsampled metadata not found at {path}\n"
                "Ensure the ingest stage completed successfully."
            )
        df = pd.read_csv(path, sep="\t", nrows=max(min_sequences + 1, 1))
        cols = set(df.columns)
        missing = BOUNDARY_REQUIRED_COLUMNS - cols
        if missing:
            raise SystemExit(
                f"Boundary check failed: subsampled metadata is missing required columns: "
                f"{sorted(missing)}\n"
                f"File: {path}\n"
                f"Present columns: {sorted(cols)}"
            )
        if min_sequences > 0:
            # Count rows: re-read just the index column for efficiency
            n_rows = sum(1 for _ in open(path)) - 1  # subtract header
            if n_rows < min_sequences:
                raise SystemExit(
                    f"Boundary check failed: subsampled dataset has only {n_rows} sequence(s), "
                    f"but qc.min_sequences={min_sequences} is required for a meaningful phylogeny.\n"
                    f"File: {path}\n"
                    "Options:\n"
                    "  • Lower qc.min_sequences in your config.yaml\n"
                    "  • Relax your subsampling strategy (subsample.yaml)\n"
                    "  • Broaden your QC thresholds (qc.genome_quality, qc.min_coverage)"
                )
            logger.info(
                "Boundary check passed (%d sequences ≥ min_sequences=%d)", n_rows, min_sequences
            )
        else:
            logger.info("Boundary check passed (%d columns present)", len(cols))

    def to_dict(self) -> dict:
        """Serialize the manifest to a plain dictionary."""
        elapsed = time.time() - self._start_time
        return {
            "run_id": self.run_id,
            "run_date": self.run_date,
            "build_name": self.build_name,
            "config_hash": self.config_hash,
            "elapsed_seconds": round(elapsed, 1),
            "status": self.extra.get("status", "unknown"),
            "counts": self.counts,
            "tool_versions": self.collect_tool_versions(),
            **self.extra,
        }

    def save(self, path: Union[str, Path]) -> None:
        """Write the manifest as pretty-printed JSON.

        Args:
            path: Output path (parent directory created if needed).
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        logger.info("Manifest written to %s (run_id=%s)", p, self.run_id)
