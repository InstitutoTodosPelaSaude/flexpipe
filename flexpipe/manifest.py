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
import subprocess
import time
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from flexpipe import __version__

logger = logging.getLogger(__name__)

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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() or result.stderr.strip() or "unknown"
    except Exception:
        return "unknown"


def _hash_config(config_path: Union[str, Path]) -> str:
    """Return a short SHA-256 digest covering config.yaml and adjacent build files."""
    try:
        config_path = Path(config_path)
        build_dir = config_path.parent
        h = hashlib.sha256()
        # Always include the config file itself (may be named config.yaml or otherwise)
        h.update(config_path.read_bytes())
        # Include other deterministic build inputs if present
        for name in sorted(["subsample.yaml", "clades.tsv", "reference.gb"]):
            candidate = build_dir / name
            if candidate.exists():
                h.update(candidate.read_bytes())
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
        self.config_hash = _hash_config(config_path) if config_path else "unknown"
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
            "augur": _run_version(["augur", "--version"]),
            "iqtree": _run_version(["iqtree3", "--version"]),
            "mafft": _run_version(["mafft", "--version"]),
        }

    def validate_boundary(self, subsampled_metadata: Union[str, Path]) -> None:
        """Assert the ingest→phylo column contract.

        Reads the header of *subsampled_metadata* and verifies that every
        column in ``BOUNDARY_REQUIRED_COLUMNS`` is present.  Raises
        ``SystemExit`` with a clear message on failure so Snakemake surfaces
        it cleanly.

        Args:
            subsampled_metadata: Path to ``results/subsampled/metadata.tsv``.
        """
        path = Path(subsampled_metadata)
        if not path.exists():
            raise SystemExit(
                f"Boundary check failed: subsampled metadata not found at {path}\n"
                "Ensure the ingest stage completed successfully."
            )
        cols = set(pd.read_csv(path, sep="\t", nrows=0).columns)
        missing = BOUNDARY_REQUIRED_COLUMNS - cols
        if missing:
            raise SystemExit(
                f"Boundary check failed: subsampled metadata is missing required columns: "
                f"{sorted(missing)}\n"
                f"File: {path}\n"
                f"Present columns: {sorted(cols)}"
            )
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
