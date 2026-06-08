"""
Geographic region lookup functions.

Provides country→continent (global builds) and Brazilian state→macro-region
(regional builds) mappings.

Extracted verbatim from ``scripts/curate.py`` (lines 19–201).

Phase 3: REGION_MAP, BRAZIL_REGION_MAP, and _BRAZIL_ABBREV are loaded from
TSV data files under ``flexpipe/data/regions/``.  A new pathogen/geography
can supply its own mapping via the ``regions.*`` config keys without editing
Python.

Division parsers can be registered without editing this module::

    from flexpipe.curate.regions import register_division_parser

    @register_division_parser("my_country")
    def parse_my_country_division(division: str, **kwargs) -> tuple[str, str]:
        # Return (canonical_division, city) tuple
        ...

The registered name is then valid as the ``regions.division_parser`` config key.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from flexpipe.data import load_data_table

logger = logging.getLogger(__name__)

# ── Division parser registry ───────────────────────────────────────────────────
_DIVISION_PARSERS: dict[str, Callable[..., tuple[str, str]]] = {}


def register_division_parser(name: str) -> Callable:
    """Decorator that registers a division parser under *name*.

    The decorated function receives ``(division: str, **kwargs)`` and must
    return a ``(canonical_division, city)`` tuple.  Extra keyword arguments
    (e.g. ``abbrev``, ``canonical``) are passed through from the orchestrator
    and may be ignored by parsers that do not need them.
    """

    def deco(fn: Callable) -> Callable:
        _DIVISION_PARSERS[name] = fn
        return fn

    return deco


def available_division_parsers() -> list[str]:
    """Return the sorted list of registered division parser names."""
    return sorted(_DIVISION_PARSERS)


# ── Public factory functions (accept optional override paths) ─────────────────


def build_region_map(override: str | Path | None = None) -> dict:
    """Build the country → continent mapping dict.

    Args:
        override: Optional path to a replacement TSV (columns: country, continent).
            When ``None`` the bundled ``country_to_continent.tsv`` is used.
    """
    df = load_data_table("flexpipe.data.regions", "country_to_continent.tsv", override=override)
    return dict(zip(df["country"], df["continent"]))


def build_brazil_maps(
    division_map_override: str | Path | None = None,
    abbrev_override: str | Path | None = None,
) -> tuple[dict, dict, dict]:
    """Build Brazilian state → region lookup structures.

    Args:
        division_map_override: Optional path to a replacement state→region TSV.
        abbrev_override: Optional path to a replacement abbreviation→state TSV.

    Returns:
        Tuple ``(region_map, norm_map, abbrev_map)`` where:

        - *region_map*: ``{canonical_state: macro_region}``
        - *norm_map*: ``{ascii_lowercased_state: macro_region}`` (accent-insensitive)
        - *abbrev_map*: ``{UF_abbreviation: canonical_state}``
    """
    region_df = load_data_table(
        "flexpipe.data.regions", "brazil_state_to_region.tsv", override=division_map_override
    )
    region_map = dict(zip(region_df["state"], region_df["region"]))

    abbrev_df = load_data_table(
        "flexpipe.data.regions", "brazil_abbreviations.tsv", override=abbrev_override
    )
    abbrev_map = dict(zip(abbrev_df["abbreviation"], abbrev_df["state"]))

    norm_map = {
        unicodedata.normalize("NFD", k).encode("ascii", "ignore").decode().lower().strip(): v
        for k, v in region_map.items()
    }
    return region_map, norm_map, abbrev_map


def build_brazil_canonical_map(region_map: dict) -> dict:
    """Build an accent-insensitive canonical-state lookup from a region map."""
    return {_normalize(k): k for k in region_map}


def _build_region_map() -> dict:
    return build_region_map()


def _build_brazil_region_map() -> dict:
    df = load_data_table("flexpipe.data.regions", "brazil_state_to_region.tsv")
    return dict(zip(df["state"], df["region"]))


def _build_brazil_abbrev() -> dict:
    df = load_data_table("flexpipe.data.regions", "brazil_abbreviations.tsv")
    return dict(zip(df["abbreviation"], df["state"]))


# ── Country → Continent (global builds) ──────────────────────────────────────
REGION_MAP = _build_region_map()

# ── Brazilian state → macro-region (division builds) ─────────────────────────
BRAZIL_REGION_MAP = _build_brazil_region_map()

# State abbreviations used in some Pathoplexus division strings (e.g. "ES, Serra [IBGE7...]")
_BRAZIL_ABBREV = _build_brazil_abbrev()

# Pre-build normalised lookups for fast accent-insensitive matching
_BRAZIL_NORM = {
    unicodedata.normalize("NFD", k).encode("ascii", "ignore").decode().lower().strip(): v
    for k, v in BRAZIL_REGION_MAP.items()
}
_ABBREV_TO_REGION = {
    abbr: BRAZIL_REGION_MAP.get(state, "") for abbr, state in _BRAZIL_ABBREV.items()
}
_BRAZIL_CANONICAL = {
    unicodedata.normalize("NFD", k).encode("ascii", "ignore").decode().lower().strip(): k
    for k in BRAZIL_REGION_MAP
}


def _normalize(s: str) -> str:
    """Strip accents, lowercase, and strip whitespace."""
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower().strip()


def lookup_region_country(country: str, region_map: dict | None = None) -> str:
    """Return the continent for a country name.

    Args:
        country: Country name string.
        region_map: Optional custom map (e.g. from :func:`build_region_map`).
            Falls back to the module-level ``REGION_MAP`` when ``None``.
    """
    m = region_map if region_map is not None else REGION_MAP
    return m.get(str(country).strip(), "")


def lookup_brazil_region(
    division: str,
    region_map: dict | None = None,
    norm_map: dict | None = None,
) -> str:
    """Return the Brazilian macro-region for a division name.

    Args:
        division: Division (state) name, possibly accent-stripped.
        region_map: Optional custom ``{state: region}`` dict.
        norm_map: Optional custom ``{ascii_state: region}`` dict.
    """
    if not division or str(division).strip() in ("", "NA"):
        return ""
    d = str(division).strip()
    rm = region_map if region_map is not None else BRAZIL_REGION_MAP
    nm = norm_map if norm_map is not None else _BRAZIL_NORM
    r = rm.get(d, "")
    if r:
        return r
    return nm.get(_normalize(d), "")


@register_division_parser("none")
def _parse_none_division(division: str, **kwargs) -> tuple[str, str]:  # noqa: ARG001
    """Identity parser — returns the division unchanged with no city extracted."""
    return division, ""


@register_division_parser("brazil")
def _parse_brazil_division(
    division_str: str,
    abbrev: dict | None = None,
    canonical: dict | None = None,
    **kwargs,
):
    """Parse a compound Pathoplexus division string into (canonical_state, city).

    Handles formats produced by Pathoplexus YFV::

        "Espírito Santo"                   → ("Espírito Santo", "")
        "Espirito Santo, Domingos Martins" → ("Espírito Santo", "Domingos Martins")
        "ES, Serra [IBGE7 3205002]"        → ("Espírito Santo", "Serra")
        "Nova Lima, Minas Gerais"          → ("Minas Gerais", "Nova Lima")
        "Domingos Martins-ES"              → ("Espírito Santo", "Domingos Martins")
        "Casimiro de Abreu-RJ"            → ("Rio de Janeiro", "Casimiro de Abreu")

    Returns:
        Tuple ``(canonical_state, city)`` where unrecognised input returns
        ``(original_string, "")``.
    """
    _abbrev = abbrev if abbrev is not None else _BRAZIL_ABBREV
    _canonical = canonical if canonical is not None else _BRAZIL_CANONICAL
    d = str(division_str).strip()
    if not d:
        return "", ""

    # Remove IBGE codes: "[IBGE7 3205002]"
    d_clean = re.sub(r"\s*\[.*?\]", "", d).strip()

    # Special case: "City-UF" (no spaces, 2-letter UF suffix)
    uf_suffix = re.match(r"^(.+?)-([A-Z]{2})$", d_clean)
    if uf_suffix:
        city_part, uf = uf_suffix.group(1).strip(), uf_suffix.group(2)
        if uf in _abbrev:
            return _abbrev[uf], city_part

    # Split on ", " or " - "
    tokens = [t.strip() for t in re.split(r",\s*|\s+-\s+", d_clean) if t.strip()]

    state_name, state_idx = "", -1
    for i, token in enumerate(tokens):
        # 2-letter abbreviation (e.g. "ES", "MG")
        if re.match(r"^[A-Z]{2}$", token) and token in _abbrev:
            state_name = _abbrev[token]
            state_idx = i
            break
        # Normalised state name (handles missing accents)
        canonical_state = _canonical.get(_normalize(token), "")
        if canonical_state:
            state_name = canonical_state
            state_idx = i
            break

    if not state_name:
        return d, ""  # unrecognised — return original, no city extracted

    city_tokens = [t for i, t in enumerate(tokens) if i != state_idx]
    city = city_tokens[0] if city_tokens else ""
    return state_name, city


def _lookup_brazil_region(division: str) -> str:
    """Return the Brazilian macro-region for a (possibly accent-stripped) division name."""
    return lookup_brazil_region(division)
