"""
Geographic region lookup functions.

Provides country→continent (global builds) and Brazilian state→macro-region
(regional builds) mappings.

Extracted verbatim from ``scripts/curate.py`` (lines 19–201).

Phase 3: REGION_MAP, BRAZIL_REGION_MAP, and _BRAZIL_ABBREV are loaded from
TSV data files under ``flexpipe/data/regions/``.  A new pathogen/geography
can supply its own mapping via the ``regions.*`` config keys without editing
Python.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from flexpipe.data import load_data_table

logger = logging.getLogger(__name__)


def _build_region_map() -> dict:
    df = load_data_table("flexpipe.data.regions", "country_to_continent.tsv")
    return dict(zip(df["country"], df["continent"]))


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


def _parse_brazil_division(division_str: str):
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
    d = str(division_str).strip()
    if not d:
        return "", ""

    # Remove IBGE codes: "[IBGE7 3205002]"
    d_clean = re.sub(r"\s*\[.*?\]", "", d).strip()

    # Special case: "City-UF" (no spaces, 2-letter UF suffix)
    uf_suffix = re.match(r"^(.+?)-([A-Z]{2})$", d_clean)
    if uf_suffix:
        city_part, uf = uf_suffix.group(1).strip(), uf_suffix.group(2)
        if uf in _BRAZIL_ABBREV:
            return _BRAZIL_ABBREV[uf], city_part

    # Split on ", " or " - "
    tokens = [t.strip() for t in re.split(r",\s*|\s+-\s+", d_clean) if t.strip()]

    state_name, state_idx = "", -1
    for i, token in enumerate(tokens):
        # 2-letter abbreviation (e.g. "ES", "MG")
        if re.match(r"^[A-Z]{2}$", token) and token in _BRAZIL_ABBREV:
            state_name = _BRAZIL_ABBREV[token]
            state_idx = i
            break
        # Normalised state name (handles missing accents)
        canonical = _BRAZIL_CANONICAL.get(_normalize(token), "")
        if canonical:
            state_name = canonical
            state_idx = i
            break

    if not state_name:
        return d, ""  # unrecognised — return original, no city extracted

    city_tokens = [t for i, t in enumerate(tokens) if i != state_idx]
    city = city_tokens[0] if city_tokens else ""
    return state_name, city


def _lookup_brazil_region(division: str) -> str:
    """Return the Brazilian macro-region for a (possibly accent-stripped) division name."""
    if not division or str(division).strip() in ("", "NA"):
        return ""
    d = str(division).strip()
    r = BRAZIL_REGION_MAP.get(d, "")
    if r:
        return r
    return _BRAZIL_NORM.get(_normalize(d), "")


def lookup_region_country(country: str) -> str:
    """Return the continent for a country name, or empty string if unknown."""
    return REGION_MAP.get(str(country).strip(), "")
