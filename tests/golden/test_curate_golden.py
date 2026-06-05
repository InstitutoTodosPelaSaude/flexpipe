"""Golden-file-style tests for the curate pipeline.

These tests run ``run_curate`` end-to-end on representative fixture input and
assert key behavioral invariants.  They pin behaviour from the refactored
package against the logic preserved from ``scripts/curate.py``.

No external tools (augur, iqtree) are needed — the pipeline step tested here
is the pure-Python ``run_curate`` function which does not shell out.
"""

from pathlib import Path

import pandas as pd
import pytest

from flexpipe.curate.pipeline import run_curate

FIXTURES = Path(__file__).parent.parent / "fixtures"
METADATA = FIXTURES / "metadata_post_augur.tsv"
VIRALQC = FIXTURES / "viralqc_results.tsv"
CONFIG_DIV = FIXTURES / "config_division_build.yaml"
CONFIG_CTY = FIXTURES / "config_country_build.yaml"


@pytest.fixture()
def curated_div(tmp_path):
    """Run curate with division (Brazil) build and return output DataFrame."""
    out = tmp_path / "curated.tsv"
    run_curate(str(CONFIG_DIV), str(METADATA), str(VIRALQC), str(out))
    return pd.read_csv(out, sep="\t", dtype=str).fillna("")


@pytest.fixture()
def curated_no_vqc(tmp_path):
    """Run curate without ViralQC to verify placeholder columns are added."""
    out = tmp_path / "curated_novqc.tsv"
    run_curate(str(CONFIG_DIV), str(METADATA), None, str(out))
    return pd.read_csv(out, sep="\t", dtype=str).fillna("")


class TestCurateOutputSchema:
    """Key columns must exist in the output."""

    def test_region_column_present(self, curated_div):
        assert "region" in curated_div.columns

    def test_clade_truncated_column_present(self, curated_div):
        assert "clade_truncated" in curated_div.columns

    def test_genome_quality_column_present(self, curated_div):
        assert "genome_quality" in curated_div.columns

    def test_coverage_column_present(self, curated_div):
        assert "coverage" in curated_div.columns

    def test_host_column_present(self, curated_div):
        assert "host" in curated_div.columns

    def test_data_use_column_present(self, curated_div):
        assert "data_use" in curated_div.columns

    def test_source_column_present(self, curated_div):
        assert "source" in curated_div.columns

    def test_ppx_raw_columns_removed(self, curated_div):
        """Pathoplexus-raw columns should have been dropped/harmonized."""
        assert "hostNameCommon" not in curated_div.columns
        assert "completeness" not in curated_div.columns


class TestCurateBrazilDivisionParsing:
    """Compound division strings are parsed to canonical state + city."""

    def test_state_comma_city_parsed(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ001"].iloc[0]
        assert row["division"] == "Espírito Santo"
        assert row["location"] == "Domingos Martins"

    def test_abbrev_comma_city_ibge_parsed(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ002"].iloc[0]
        assert row["division"] == "Espírito Santo"
        assert row["location"] == "Serra"

    def test_city_comma_state_parsed(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ003"].iloc[0]
        assert row["division"] == "Minas Gerais"
        # Nova Lima was already in location column — should be preserved
        assert row["location"] == "Nova Lima"


class TestCurateRegionAssignment:
    """Region must be correctly derived from division (Brazil build)."""

    def test_espirito_santo_is_sudeste(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ001"].iloc[0]
        assert row["region"] == "Sudeste"

    def test_minas_gerais_is_sudeste(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ003"].iloc[0]
        assert row["region"] == "Sudeste"

    def test_amazonas_is_norte(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ007"].iloc[0]
        assert row["region"] == "Norte"

    def test_para_is_norte(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ008"].iloc[0]
        assert row["region"] == "Norte"

    def test_sao_paulo_is_sudeste(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ005"].iloc[0]
        assert row["region"] == "Sudeste"


class TestCurateCladeLevel:
    """clade_truncated must respect clade_levels=1."""

    def test_level_1_truncation(self, curated_div):
        """'I.A' with clade_levels=1 → 'I'."""
        row = curated_div[curated_div["strain"] == "SEQ008"].iloc[0]
        assert row["clade_truncated"] == "I"

    def test_single_level_clade_unchanged(self, curated_div):
        """'I' is already level 1 — should be unchanged."""
        row = curated_div[curated_div["strain"] == "SEQ001"].iloc[0]
        assert row["clade_truncated"] == "I"


class TestCurateHostNormalization:
    """Host names normalized via the rule table."""

    def test_homo_sapiens_to_human(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ001"].iloc[0]
        assert row["host"] == "human"

    def test_mosquito_normalized(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ002"].iloc[0]
        assert row["host"] == "mosquito"

    def test_haemagogus_fallback(self, curated_div):
        """haemagogus janthinomys has no rule → lowercased fallback.
        The HOST_HUES table maps it to the mosquito color bucket separately."""
        row = curated_div[curated_div["strain"] == "SEQ007"].iloc[0]
        assert row["host"] == "haemagogus janthinomys"

    def test_primate_kept(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ008"].iloc[0]
        assert row["host"] == "primate"


class TestCurateViralQCJoin:
    """ViralQC columns merged correctly."""

    def test_genome_quality_a_set(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ001"].iloc[0]
        assert row["genome_quality"] == "A"

    def test_genome_quality_c_set(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ005"].iloc[0]
        assert row["genome_quality"] == "C"

    def test_genome_quality_d_set(self, curated_div):
        row = curated_div[curated_div["strain"] == "SEQ006"].iloc[0]
        assert row["genome_quality"] == "D"


class TestCurateDataUseUppercase:
    """data_use must be uppercased."""

    def test_open_uppercased(self, curated_div):
        # All fixture rows have dataUseTerms=OPEN; the curate pipeline
        # maps it to data_use (after harmonization from dataUseTerms column).
        # NOTE: curate doesn't rename dataUseTerms → data_use here — augur
        # curate rename does that upstream. The fixture already has the
        # right column name.
        # The data_use column from the fixture is uppercase-normalised.
        data_use_values = set(curated_div["data_use"].dropna())
        assert "OPEN" in data_use_values


class TestCurateDeduplication:
    """Duplicate strains are removed."""

    def test_no_duplicate_strains(self, curated_div):
        assert curated_div["strain"].nunique() == len(curated_div)


class TestCurateNoViralqc:
    """run_curate with no ViralQC file still produces required columns."""

    def test_genome_quality_placeholder(self, curated_no_vqc):
        assert "genome_quality" in curated_no_vqc.columns

    def test_coverage_placeholder(self, curated_no_vqc):
        assert "coverage" in curated_no_vqc.columns

    def test_region_still_assigned(self, curated_no_vqc):
        """Region assignment should work even without ViralQC."""
        row = curated_no_vqc[curated_no_vqc["strain"] == "SEQ001"].iloc[0]
        assert row["region"] == "Sudeste"
