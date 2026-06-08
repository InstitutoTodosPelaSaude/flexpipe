"""Unit tests for flexpipe.colors.hues — spread_hues and collect."""

import pandas as pd

from flexpipe.colors.hues import (
    CLADE_HUES,
    DATA_USE_HUES,
    HOST_HUES,
    REGION_HUES,
    SOURCE_HUES,
    VALID_HUES,
    _natural_key,
    collect,
    load_hue_cache,
    spread_hues,
    stable_hash_hue,
    write_hue_cache,
)


class TestNaturalKey:
    """Tests for ``_natural_key`` sort key."""

    def test_pure_text_alphabetical(self):
        names = ["Bravo", "Alpha", "Charlie"]
        assert sorted(names, key=_natural_key) == ["Alpha", "Bravo", "Charlie"]

    def test_numeric_suffix_sorted_numerically(self):
        """A.D.10 must sort after A.D.2, not before (lexicographic would give wrong order)."""
        names = ["A.D.10", "A.D.2", "A.D.1"]
        assert sorted(names, key=_natural_key) == ["A.D.1", "A.D.2", "A.D.10"]

    def test_mixed(self):
        names = ["B.1.1", "B.1.10", "B.1.2"]
        assert sorted(names, key=_natural_key) == ["B.1.1", "B.1.2", "B.1.10"]


class TestSpreadHues:
    """Tests for ``spread_hues``."""

    def test_empty_returns_empty(self):
        assert spread_hues([]) == {}

    def test_single_item(self):
        result = spread_hues(["A"])
        assert len(result) == 1
        assert result["A"] in VALID_HUES

    def test_all_hues_in_valid_set(self):
        names = [f"clade{i}" for i in range(12)]
        result = spread_hues(names)
        for hue in result.values():
            assert hue in VALID_HUES, f"Invalid hue: {hue}"

    def test_all_hues_distinct(self):
        names = [f"clade{i}" for i in range(6)]
        result = spread_hues(names)
        assert len(set(result.values())) == len(names)

    def test_step_multiples_of_ten(self):
        names = ["A", "B", "C", "D", "E", "F"]  # 6 names → step=60
        result = spread_hues(names)
        hues = sorted(result.values())
        assert all(h % 10 == 0 for h in hues)

    def test_deterministic_same_names(self):
        """Same names → same hues on repeated calls."""
        names = ["I", "II", "III", "IV"]
        assert spread_hues(names) == spread_hues(names)

    def test_sorted_alphabetically(self):
        """Alphabetically first name gets the lowest hue."""
        result = spread_hues(["B", "A"])
        assert result["A"] < result["B"]

    def test_numeric_sort_within_spread(self):
        """Numeric suffixes sorted numerically (not lexicographically)."""
        result = spread_hues(["A.2", "A.10", "A.1"])
        # A.1 is alphabetically/numerically first → lowest hue
        assert result["A.1"] < result["A.2"] < result["A.10"]


class TestCollect:
    """Tests for ``collect(df, col, fixed_hues, label, use_hash_for_unknown)``."""

    def _df(self, col_values):
        return pd.DataFrame({col_values[0]: col_values[1]})

    def test_known_values_get_fixed_hue(self):
        df = pd.DataFrame({"region": ["Norte", "Sudeste"]})
        result, warns = collect(df, "region", REGION_HUES, "region")
        assert result["Norte"] == REGION_HUES["Norte"]
        assert result["Sudeste"] == REGION_HUES["Sudeste"]
        assert warns == []

    def test_unknown_value_gets_hue_and_warning(self):
        df = pd.DataFrame({"region": ["NewContinent"]})
        result, warns = collect(df, "region", REGION_HUES, "region")
        assert "NewContinent" in result
        assert result["NewContinent"] in VALID_HUES
        assert len(warns) == 1

    def test_unknown_uses_hash_spread(self):
        df = pd.DataFrame({"clade_truncated": ["I", "II", "III"]})
        result, warns = collect(
            df, "clade_truncated", CLADE_HUES, "clade", use_hash_for_unknown=True
        )
        assert len(result) == 3
        # All hues should be valid multiples of 10
        for hue in result.values():
            assert hue in VALID_HUES

    def test_hash_spread_deterministic(self):
        """Same clade names → same hue assignment regardless of call order."""
        df = pd.DataFrame({"clade_truncated": ["I", "II", "III"]})
        r1, _ = collect(df, "clade_truncated", CLADE_HUES, "clade", use_hash_for_unknown=True)
        r2, _ = collect(df, "clade_truncated", CLADE_HUES, "clade", use_hash_for_unknown=True)
        assert r1 == r2

    def test_hash_hue_stable_when_clade_set_grows(self):
        df1 = pd.DataFrame({"clade_truncated": ["clade_A"]})
        df2 = pd.DataFrame({"clade_truncated": ["clade_A", "clade_B"]})
        r1, _ = collect(df1, "clade_truncated", CLADE_HUES, "clade", use_hash_for_unknown=True)
        r2, _ = collect(df2, "clade_truncated", CLADE_HUES, "clade", use_hash_for_unknown=True)
        assert r1["clade_A"] == r2["clade_A"]

    def test_cached_hue_preserved_for_unknown(self):
        df = pd.DataFrame({"clade_truncated": ["clade_A", "clade_B"]})
        result, _ = collect(
            df,
            "clade_truncated",
            CLADE_HUES,
            "clade",
            use_hash_for_unknown=True,
            cached_hues={"clade_A": 230},
        )
        assert result["clade_A"] == 230

    def test_fixed_hue_overrides_cache(self):
        df = pd.DataFrame({"region": ["Norte"]})
        result, _ = collect(df, "region", REGION_HUES, "region", cached_hues={"Norte": 10})
        assert result["Norte"] == REGION_HUES["Norte"]

    def test_empty_values_excluded(self):
        df = pd.DataFrame({"region": ["Norte", "", "NA", "nan"]})
        result, _ = collect(df, "region", REGION_HUES, "region")
        assert "" not in result
        assert "NA" not in result
        assert "nan" not in result
        assert "Norte" in result

    def test_missing_column_returns_empty(self):
        """Missing column is logged as a warning and returns ({}, []).
        The log goes to the logger, not to the returned warns list."""
        df = pd.DataFrame({"other_col": ["x"]})
        result, warns = collect(df, "region", REGION_HUES, "region")
        assert result == {}
        assert warns == []  # warning emitted via logger, not returned

    def test_source_hues_known_values(self):
        df = pd.DataFrame({"source": ["ITpS", "Pathoplexus", "NCBI"]})
        result, warns = collect(df, "source", SOURCE_HUES, "source")
        assert result["ITpS"] == SOURCE_HUES["ITpS"]
        assert result["NCBI"] == SOURCE_HUES["NCBI"]
        assert warns == []


class TestHueTables:
    """Sanity checks on the hue tables themselves."""

    def test_all_region_hues_valid(self):
        for name, hue in REGION_HUES.items():
            assert hue in VALID_HUES, f"Invalid hue for {name}: {hue}"

    def test_all_source_hues_valid(self):
        for name, hue in SOURCE_HUES.items():
            assert hue in VALID_HUES, f"Invalid hue for {name}: {hue}"

    def test_all_host_hues_valid(self):
        for name, hue in HOST_HUES.items():
            assert hue in VALID_HUES, f"Invalid hue for {name}: {hue}"

    def test_all_data_use_hues_valid(self):
        for name, hue in DATA_USE_HUES.items():
            assert hue in VALID_HUES, f"Invalid hue for {name}: {hue}"

    def test_clade_hues_intentionally_empty(self):
        """CLADE_HUES is intentionally empty — hash fallback handles clades."""
        assert CLADE_HUES == {}


class TestHueCache:
    def test_stable_hash_bucket_is_valid_and_deterministic(self):
        assert stable_hash_hue("clade_A") == stable_hash_hue("clade_A")
        assert stable_hash_hue("clade_A") in VALID_HUES

    def test_load_and_write_hue_cache(self, tmp_path):
        cache = tmp_path / "name2hue.tsv"
        write_hue_cache(cache, {"clade_A": 120, "clade_B": 240})
        assert load_hue_cache(cache) == {"clade_A": 120, "clade_B": 240}
