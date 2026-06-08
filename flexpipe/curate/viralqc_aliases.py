"""Alias-aware matching for ViralQC virus and segment labels."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from flexpipe.data import load_data_yaml

logger = logging.getLogger(__name__)

AliasKind = Literal["viruses", "segments"]


@dataclass(frozen=True)
class AliasEntry:
    """Resolved aliases and patterns for one expected ViralQC label."""

    key: str
    aliases: tuple[str, ...]
    patterns: tuple[str, ...]
    ictv_species: str = ""


def normalize_label(value: object) -> str:
    """Return a comparison-friendly representation of a ViralQC label."""
    text = str(value or "").casefold().strip()
    text = re.sub(r"[_/()]+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_registry(override: str | Path | None = None) -> dict[str, Any]:
    data = load_data_yaml("flexpipe.data.viralqc", "aliases.yaml", override=override)
    if not isinstance(data, dict):
        raise ValueError("ViralQC alias registry must be a YAML mapping")
    return data


@lru_cache(maxsize=16)
def _load_registry_cached(override: str = "") -> dict[str, Any]:
    return _load_registry(override or None)


def load_alias_registry(override: str | Path | None = None) -> dict[str, Any]:
    """Load the bundled ViralQC alias registry, or an override file."""
    return _load_registry_cached(str(override or ""))


def _coerce_entry(key: str, raw: Any) -> AliasEntry:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"ViralQC alias entry '{key}' must be a mapping")
    aliases = [key, *raw.get("aliases", [])]
    ictv_species = str(raw.get("ictv_species", "") or "").strip()
    return AliasEntry(
        key=key,
        aliases=tuple(str(alias) for alias in aliases if str(alias).strip()),
        patterns=tuple(str(pattern) for pattern in raw.get("patterns", []) if str(pattern).strip()),
        ictv_species=ictv_species,
    )


def _collection(registry: dict[str, Any], kind: AliasKind) -> dict[str, AliasEntry]:
    raw = registry.get(kind, {}) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"ViralQC alias registry section '{kind}' must be a mapping")
    return {str(key): _coerce_entry(str(key), value) for key, value in raw.items()}


def resolve_expected_entry(
    expected: str | None,
    kind: AliasKind,
    *,
    aliases_file: str | Path | None = None,
) -> AliasEntry | None:
    """Resolve an expected label to a registry entry or an ad-hoc exact entry.

    The expected value can be a canonical registry key, any alias in the registry,
    or a literal label. Literal labels preserve backwards-compatible exact matching.
    """
    if not expected or not str(expected).strip():
        return None

    expected_text = str(expected).strip()
    expected_norm = normalize_label(expected_text)
    registry = load_alias_registry(aliases_file)
    entries = _collection(registry, kind)

    for entry in entries.values():
        if expected_norm == normalize_label(entry.key):
            return entry
        if expected_norm in {normalize_label(alias) for alias in entry.aliases}:
            return entry

    logger.debug("No ViralQC alias entry for %s=%r; falling back to exact matching", kind, expected)
    return AliasEntry(key=expected_text, aliases=(expected_text,), patterns=())


def label_matches_entry(observed: object, entry: AliasEntry) -> bool:
    """Return True when *observed* matches an alias entry."""
    observed_text = str(observed or "").strip()
    if not observed_text:
        return False

    observed_norm = normalize_label(observed_text)
    alias_norms = {normalize_label(alias) for alias in entry.aliases}
    if observed_norm in alias_norms:
        return True

    for pattern in entry.patterns:
        if re.search(pattern, observed_text, flags=re.IGNORECASE):
            return True
        if re.search(pattern, observed_norm, flags=re.IGNORECASE):
            return True
    return False


def labels_match_expected(
    observed: object,
    expected: str | None,
    kind: AliasKind,
    *,
    aliases_file: str | Path | None = None,
) -> bool:
    """Return whether *observed* is accepted for the configured expected label."""
    entry = resolve_expected_entry(expected, kind, aliases_file=aliases_file)
    if entry is None:
        return True
    return label_matches_entry(observed, entry)
