"""Optional lineage parsers for curated metadata.

The raw Nextclade/ViralQC lineage remains in ``clade``.  Parsers add derived,
prefix-safe columns that can be used for filtering, coloring, and traits.

New parsers can be registered without editing this module::

    from flexpipe.curate.lineage_parser import register_parser

    @register_parser("my_pathogen")
    def parse_my_lineage(clade: object) -> dict[str, str]:
        ...
        return {"serotype": ..., "genotype": ..., ...}

The registered name is then valid as the ``curation.lineage_parser`` config key.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping

import pandas as pd

logger = logging.getLogger(__name__)

LINEAGE_KEYS = ("serotype", "genotype", "major_lineage", "minor_lineage")

# ── Parser registry ────────────────────────────────────────────────────────────
_PARSERS: dict[str, Callable[[object], dict[str, str]]] = {}


def register_parser(name: str) -> Callable:
    """Decorator that registers a lineage parser under *name*.

    The decorated function must accept a clade string (or ``None``/empty) and
    return a ``dict`` with a subset of :data:`LINEAGE_KEYS`.  Missing keys are
    treated as empty strings by :func:`apply_lineage_parser`.
    """

    def deco(fn: Callable) -> Callable:
        _PARSERS[name] = fn
        return fn

    return deco


def available_parsers() -> list[str]:
    """Return the sorted list of registered parser names."""
    return sorted(_PARSERS)


# ── DENV regexes ──────────────────────────────────────────────────────────────

_DENV_RE = re.compile(
    r"^(?P<serotype>[1-4])"
    r"(?P<genotype>[IVX]+)"
    r"(?:_(?P<major>[A-Za-z]+)(?P<minor>(?:\.[A-Za-z0-9]+)+)?)?$"
)
_SEROTYPE_RE = re.compile(r"^(?:DENV[-_\s]*)?(?P<serotype>[1-4])$", re.IGNORECASE)


def normalize_serotype(value: object) -> str:
    """Return a compact DENV serotype number when *value* is recognizable."""
    text = str(value or "").strip()
    if not text:
        return ""
    match = _SEROTYPE_RE.match(text)
    return match.group("serotype") if match else text


@register_parser("dengue")
def parse_dengue_lineage(clade: object) -> dict[str, str]:
    """Parse DENV lineage strings into prefix-safe hierarchy levels.

    Examples:
        ``1V_E.1`` → ``1``, ``1V``, ``1V_E``, ``1V_E.1``
        ``3III_B.3.2`` → ``3``, ``3III``, ``3III_B``, ``3III_B.3.2``
        ``4I`` → ``4``, ``4I``, ``""``, ``""``
    """
    text = str(clade or "").strip()
    if not text:
        return {}
    match = _DENV_RE.match(text)
    if not match:
        return {}

    serotype = match.group("serotype")
    genotype = f"{serotype}{match.group('genotype')}"
    major = match.group("major") or ""
    major_lineage = f"{genotype}_{major}" if major else ""
    minor = match.group("minor") or ""
    minor_lineage = f"{major_lineage}{minor}" if major_lineage and minor else ""
    return {
        "serotype": serotype,
        "genotype": genotype,
        "major_lineage": major_lineage,
        "minor_lineage": minor_lineage,
    }


@register_parser("pango")
@register_parser("generic_dot")
def parse_generic_dot_lineage(clade: object) -> dict[str, str]:
    """Parse dot-separated names into broad, prefix-preserving levels."""
    text = str(clade or "").strip()
    if not text:
        return {}
    parts = [part for part in text.split(".") if part]
    if not parts:
        return {}

    genotype = parts[0]
    major = ".".join(parts[:2]) if len(parts) >= 2 else ""
    minor = text if len(parts) >= 3 else ""
    return {
        "serotype": "",
        "genotype": genotype,
        "major_lineage": major,
        "minor_lineage": minor,
    }


@register_parser("none")
def _parse_none_lineage(clade: object) -> dict[str, str]:  # noqa: ARG001
    """No-op parser — returns an empty dict (no derived lineage columns)."""
    return {}


def parse_lineage(clade: object, parser: str) -> dict[str, str]:
    """Parse *clade* using a named parser.

    Raises:
        ValueError: If *parser* is not registered.  The message lists
            all :func:`available_parsers`.
    """
    if parser not in _PARSERS:
        raise ValueError(
            f"Unsupported lineage parser: {parser!r}. " f"Available parsers: {available_parsers()}"
        )
    return _PARSERS[parser](clade)


def apply_lineage_parser(
    df: pd.DataFrame,
    *,
    parser: str,
    columns: Mapping[str, str],
    clade_column: str = "clade",
) -> pd.DataFrame:
    """Populate derived lineage columns on *df*.

    ``parser='none'`` intentionally leaves the frame unchanged.  For DENV, the
    configured serotype column is normalized from values like ``DENV-3`` and then
    reconciled with the parsed serotype from ``clade``.
    """
    if parser == "none":
        return df
    if parser not in _PARSERS:
        raise ValueError(
            f"Unsupported lineage parser: {parser!r}. " f"Available parsers: {available_parsers()}"
        )
    if clade_column not in df.columns:
        logger.warning(
            "Lineage parser %s requested but '%s' column is missing", parser, clade_column
        )
        return df

    out = df.copy()
    parsed = out[clade_column].apply(lambda value: parse_lineage(value, parser))
    parsed_count = sum(1 for item in parsed if item)
    malformed_count = sum(
        1 for raw, item in zip(out[clade_column], parsed) if str(raw).strip() and not item
    )

    output_columns = {key: columns.get(key, key) for key in LINEAGE_KEYS}
    for key, out_col in output_columns.items():
        values = parsed.apply(lambda item, k=key: item.get(k, "") if item else "")
        if key == "serotype":
            existing = (
                out[out_col].apply(normalize_serotype)
                if out_col in out.columns
                else pd.Series([""] * len(out), index=out.index)
            )
            conflicts = (
                (existing.str.strip() != "") & (values.str.strip() != "") & (existing != values)
            )
            conflict_count = int(conflicts.sum())
            if conflict_count:
                logger.warning(
                    "Lineage parser %s found %d serotype conflicts; parsed clade values win",
                    parser,
                    conflict_count,
                )
            out[out_col] = values.where(values.str.strip() != "", existing)
        else:
            out[out_col] = values

    logger.info(
        "Lineage parser %s parsed %d/%d rows; malformed non-empty clades: %d",
        parser,
        parsed_count,
        len(out),
        malformed_count,
    )
    return out
