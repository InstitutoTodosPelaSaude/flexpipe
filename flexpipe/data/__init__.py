"""
Bundled reference data for flexpipe.

Provides ``load_data_table()`` and ``load_data_yaml()`` helpers that resolve:
  1. An explicit override path (from config or CLI)
  2. The bundled default packaged with the library (``importlib.resources``)

This lets a new pathogen override region maps, host rules, or hue tables by
pointing to a custom file in its ``config.yaml`` without editing Python.
"""

from __future__ import annotations

import logging
from typing import Any
from importlib.resources import files
from pathlib import Path

import pandas as pd
import yaml

logger = logging.getLogger(__name__)


def load_data_table(
    package: str,
    filename: str,
    override: str | Path | None = None,
    comment: str = "#",
) -> pd.DataFrame:
    """Load a TSV reference table from an override path or the bundled default.

    Args:
        package: Dot-path to the sub-package containing the bundled file
            (e.g. ``"flexpipe.data.regions"``).
        filename: File name within *package* (e.g. ``"country_to_continent.tsv"``).
        override: Optional path to a user-supplied replacement file.  When
            provided and the file exists, it is used instead of the bundled
            default.
        comment: Lines starting with this character are skipped (default ``"#"``).

    Returns:
        DataFrame with ``str`` dtype and empty strings instead of NaN.
    """
    if override:
        p = Path(override)
        if not p.exists():
            raise FileNotFoundError(
                f"Data override not found: {p}\n"
                f"(The bundled default for {package}/{filename} would have been used.)"
            )
        logger.debug("Loading data override: %s", p)
        return pd.read_csv(p, sep="\t", dtype=str, comment=comment).fillna("")

    resource = files(package) / filename
    logger.debug("Loading bundled data: %s/%s", package, filename)
    with resource.open("r", encoding="utf-8") as fh:
        return pd.read_csv(fh, sep="\t", dtype=str, comment=comment).fillna("")


def load_data_yaml(
    package: str,
    filename: str,
    override: str | Path | None = None,
) -> Any:
    """Load a YAML reference file from an override path or the bundled default.

    Args:
        package: Dot-path to the sub-package (e.g. ``"flexpipe.data.hosts"``).
        filename: File name (e.g. ``"host_rules.yaml"``).
        override: Optional path to a user-supplied replacement file.

    Returns:
        The parsed YAML object (typically a ``dict`` or ``list``).
    """
    if override:
        p = Path(override)
        if not p.exists():
            raise FileNotFoundError(
                f"Data override not found: {p}\n"
                f"(The bundled default for {package}/{filename} would have been used.)"
            )
        logger.debug("Loading YAML override: %s", p)
        return yaml.safe_load(p.read_text(encoding="utf-8"))

    resource = files(package) / filename
    logger.debug("Loading bundled YAML: %s/%s", package, filename)
    with resource.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
