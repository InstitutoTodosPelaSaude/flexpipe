"""Unit tests for optional lineage decomposition."""

import pandas as pd

from flexpipe.curate.lineage_parser import (
    apply_lineage_parser,
    normalize_serotype,
    parse_dengue_lineage,
    parse_generic_dot_lineage,
)


def test_normalize_serotype():
    assert normalize_serotype("DENV-3") == "3"
    assert normalize_serotype("denv 4") == "4"
    assert normalize_serotype("2") == "2"
    assert normalize_serotype("") == ""


def test_parse_dengue_prefixed_lineage_examples():
    assert parse_dengue_lineage("1V_E.1") == {
        "serotype": "1",
        "genotype": "1V",
        "major_lineage": "1V_E",
        "minor_lineage": "1V_E.1",
    }
    assert parse_dengue_lineage("3III_B.3.2") == {
        "serotype": "3",
        "genotype": "3III",
        "major_lineage": "3III_B",
        "minor_lineage": "3III_B.3.2",
    }
    assert parse_dengue_lineage("4I") == {
        "serotype": "4",
        "genotype": "4I",
        "major_lineage": "",
        "minor_lineage": "",
    }


def test_parse_dengue_empty_or_malformed_returns_empty():
    assert parse_dengue_lineage("") == {}
    assert parse_dengue_lineage("not-a-lineage") == {}
    assert parse_dengue_lineage(None) == {}


def test_parse_generic_dot_is_prefix_preserving():
    assert parse_generic_dot_lineage("BA.5.2.1") == {
        "serotype": "",
        "genotype": "BA",
        "major_lineage": "BA.5",
        "minor_lineage": "BA.5.2.1",
    }


def test_apply_lineage_parser_preserves_raw_clade_and_normalizes_serotype():
    df = pd.DataFrame({"clade": ["3III_B.3.2", "4I"], "serotype": ["DENV-3", "DENV-4"]})

    out = apply_lineage_parser(
        df,
        parser="dengue",
        columns={
            "serotype": "serotype",
            "genotype": "genotype",
            "major_lineage": "major_lineage",
            "minor_lineage": "minor_lineage",
        },
    )

    assert out["clade"].tolist() == ["3III_B.3.2", "4I"]
    assert out["serotype"].tolist() == ["3", "4"]
    assert out["genotype"].tolist() == ["3III", "4I"]
    assert out["major_lineage"].tolist() == ["3III_B", ""]
    assert out["minor_lineage"].tolist() == ["3III_B.3.2", ""]


def test_parser_none_leaves_frame_unchanged():
    df = pd.DataFrame({"clade": ["3III_B.3.2"]})
    out = apply_lineage_parser(df, parser="none", columns={})
    assert out.equals(df)
