"""Unit tests for flexpipe.curate.regions."""

import pytest

from flexpipe.curate.regions import (
    _lookup_brazil_region,
    _parse_brazil_division,
    lookup_region_country,
)


class TestParseBrazilDivision:
    """Tests for ``_parse_brazil_division`` — all Pathoplexus compound formats."""

    def test_plain_state_with_accents(self):
        state, city = _parse_brazil_division("Espírito Santo")
        assert state == "Espírito Santo"
        assert city == ""

    def test_plain_state_without_accents(self):
        """Accent-stripped state names must still match."""
        state, city = _parse_brazil_division("Espirito Santo")
        assert state == "Espírito Santo"
        assert city == ""

    def test_state_comma_city(self):
        """'State, City' format."""
        state, city = _parse_brazil_division("Espírito Santo, Domingos Martins")
        assert state == "Espírito Santo"
        assert city == "Domingos Martins"

    def test_abbrev_comma_city_with_ibge(self):
        """'UF, City [IBGE7 …]' format — IBGE code stripped."""
        state, city = _parse_brazil_division("ES, Serra [IBGE7 3205002]")
        assert state == "Espírito Santo"
        assert city == "Serra"

    def test_city_comma_state(self):
        """'City, State' — state detected after city."""
        state, city = _parse_brazil_division("Nova Lima, Minas Gerais")
        assert state == "Minas Gerais"
        assert city == "Nova Lima"

    def test_city_dash_uf_no_spaces(self):
        """'City-UF' compact format."""
        state, city = _parse_brazil_division("Domingos Martins-ES")
        assert state == "Espírito Santo"
        assert city == "Domingos Martins"

    def test_city_dash_uf_rj(self):
        state, city = _parse_brazil_division("Casimiro de Abreu-RJ")
        assert state == "Rio de Janeiro"
        assert city == "Casimiro de Abreu"

    def test_state_abbreviation_alone(self):
        """Bare 2-letter abbreviation."""
        state, city = _parse_brazil_division("SP")
        assert state == "São Paulo"
        assert city == ""

    def test_unrecognised_returns_original(self):
        """Strings that don't match any state must return the original string unchanged."""
        state, city = _parse_brazil_division("Narnia")
        assert state == "Narnia"
        assert city == ""

    def test_empty_string(self):
        state, city = _parse_brazil_division("")
        assert state == ""
        assert city == ""

    def test_all_27_states_recognized(self):
        """Every canonical state name must parse to itself."""
        from flexpipe.curate.regions import BRAZIL_REGION_MAP
        for state_name in BRAZIL_REGION_MAP:
            s, _ = _parse_brazil_division(state_name)
            assert s == state_name, f"Failed for: {state_name!r}"

    def test_all_abbrevs_recognized(self):
        """Every 2-letter abbreviation must parse to its full state name."""
        from flexpipe.curate.regions import _BRAZIL_ABBREV
        for abbr, expected_state in _BRAZIL_ABBREV.items():
            s, _ = _parse_brazil_division(abbr)
            assert s == expected_state, f"Abbreviation {abbr!r} did not map to {expected_state!r}"


class TestLookupBrazilRegion:
    """Tests for ``_lookup_brazil_region``."""

    def test_exact_match_with_accents(self):
        assert _lookup_brazil_region("Espírito Santo") == "Sudeste"

    def test_accent_insensitive(self):
        """Missing accents should still match via normalized lookup."""
        assert _lookup_brazil_region("Espirito Santo") == "Sudeste"

    def test_all_five_regions_covered(self):
        samples = {
            "Amazonas": "Norte",
            "Ceará": "Nordeste",
            "Goiás": "Centro-Oeste",
            "São Paulo": "Sudeste",
            "Paraná": "Sul",
        }
        for state, expected_region in samples.items():
            assert _lookup_brazil_region(state) == expected_region

    def test_empty_returns_empty(self):
        assert _lookup_brazil_region("") == ""

    def test_na_returns_empty(self):
        assert _lookup_brazil_region("NA") == ""

    def test_unknown_division_returns_empty(self):
        assert _lookup_brazil_region("Narnia") == ""


class TestLookupRegionCountry:
    """Tests for ``lookup_region_country``."""

    def test_brazil(self):
        assert lookup_region_country("Brazil") == "South America"

    def test_usa(self):
        assert lookup_region_country("United States") == "North America"

    def test_usa_alias(self):
        assert lookup_region_country("USA") == "North America"

    def test_nigeria(self):
        assert lookup_region_country("Nigeria") == "Africa"

    def test_japan(self):
        assert lookup_region_country("Japan") == "Asia"

    def test_unknown_returns_empty(self):
        assert lookup_region_country("Wakanda") == ""

    def test_strip_whitespace(self):
        assert lookup_region_country("  Brazil  ") == "South America"
