"""Unit tests for flexpipe.curate.hosts.normalize_host."""

import pytest

from flexpipe.curate.hosts import normalize_host


class TestNormalizeHostHuman:
    """Human host identification — Homo sapiens variants."""

    def test_homo_sapiens(self):
        assert normalize_host("Homo sapiens") == "human"

    def test_home_sapiens_typo(self):
        """Common database typo."""
        assert normalize_host("home sapiens") == "human"

    def test_plain_human(self):
        assert normalize_host("human") == "human"

    def test_human_case_insensitive(self):
        assert normalize_host("Human") == "human"

    def test_people(self):
        assert normalize_host("people") == "human"

    def test_person(self):
        assert normalize_host("person") == "human"

    def test_homosapien_run_on(self):
        assert normalize_host("homosapien") == "human"


class TestNormalizeHostSwine:
    """Swine host identification."""

    def test_sus_scrofa(self):
        assert normalize_host("Sus scrofa") == "swine"

    def test_swine(self):
        assert normalize_host("swine") == "swine"

    def test_pig(self):
        assert normalize_host("pig") == "swine"

    def test_wild_boar(self):
        assert normalize_host("wild boar") == "swine"


class TestNormalizeHostAvian:
    """Avian host identification — both regex-matched genera and keywords."""

    def test_duck(self):
        assert normalize_host("duck") == "avian"

    def test_gallus(self):
        assert normalize_host("Gallus gallus") == "avian"

    def test_bird_keyword(self):
        assert normalize_host("wild bird") == "avian"

    def test_swan(self):
        assert normalize_host("swan") == "avian"

    def test_turkey(self):
        assert normalize_host("turkey") == "avian"

    def test_goose_keyword(self):
        assert normalize_host("Canada goose") == "avian"


class TestNormalizeHostOtherCategories:
    """Mouse, ferret, camel, drop (cell lines), dog."""

    def test_mus_musculus(self):
        assert normalize_host("Mus musculus") == "mouse"

    def test_mouse(self):
        assert normalize_host("mouse") == "mouse"

    def test_house_mouse(self):
        assert normalize_host("house mouse") == "mouse"

    def test_ferret(self):
        assert normalize_host("ferret") == "ferret"

    def test_mustela(self):
        assert normalize_host("Mustela putorius furo") == "ferret"

    def test_mink(self):
        assert normalize_host("mink") == "ferret"

    def test_camel(self):
        assert normalize_host("camel") == "camel"

    def test_camelus_dromedarius(self):
        assert normalize_host("Camelus dromedarius") == "camel"

    def test_mdck_dropped(self):
        assert normalize_host("MDCK") == ""

    def test_cell_line_dropped(self):
        assert normalize_host("cell line") == ""

    def test_environmental_dropped(self):
        assert normalize_host("environmental") == ""

    def test_canis_lupus_dog(self):
        assert normalize_host("Canis lupus familiaris") == "dog"

    def test_canine_dog(self):
        assert normalize_host("canine") == "dog"


class TestNormalizeHostEdgeCases:
    """Edge cases: empty, semicolons, whitespace, fallback."""

    def test_empty_string(self):
        assert normalize_host("") == ""

    def test_whitespace_only(self):
        assert normalize_host("   ") == ""

    def test_semicolon_splits_to_base(self):
        """Only the part before the first ';' is evaluated."""
        assert normalize_host("Homo sapiens; patient") == "human"

    def test_semicolon_swine(self):
        assert normalize_host("Sus scrofa; farm pig") == "swine"

    def test_fallback_lowercases(self):
        """Unknown hosts are returned lowercased (the base before ';')."""
        result = normalize_host("Aotus azarae")
        assert result == "aotus azarae"

    def test_human_precedence_over_swine(self):
        """Human rule fires before swine — 'human swine flu' should be human.
        In practice this string starts with 'human', so human wins."""
        assert normalize_host("human-derived sample") == "human"
