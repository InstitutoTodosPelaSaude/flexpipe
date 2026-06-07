"""Unit tests for TreeTime trait-state collapsing."""

import pandas as pd

from flexpipe.phylo.traits import collapse_trait_states


def test_collapse_keeps_most_frequent_states_and_maps_rare_to_other():
    df = pd.DataFrame({"location": ["A", "A", "A", "B", "B", "C", "D", ""]})

    out, rows = collapse_trait_states(
        df,
        ["location"],
        max_states=3,
        rare_state_label="other",
    )

    assert out["location"].tolist() == ["A", "A", "A", "B", "B", "other", "other", ""]
    assert {(row["state"], row["count"]) for row in rows} == {("C", 1), ("D", 1)}


def test_collapse_ties_by_natural_sort():
    df = pd.DataFrame({"lineage": ["state10", "state2", "state1"]})

    out, rows = collapse_trait_states(df, ["lineage"], max_states=2)

    assert out["lineage"].tolist() == ["other", "other", "state1"]
    assert [row["state"] for row in rows] == ["state2", "state10"]


def test_collapse_applies_to_all_configured_columns():
    df = pd.DataFrame(
        {
            "country": ["A", "B", "C"],
            "clade": ["X", "Y", "Z"],
        }
    )

    out, rows = collapse_trait_states(df, ["country", "clade"], max_states=2)

    assert out["country"].tolist() == ["A", "other", "other"]
    assert out["clade"].tolist() == ["X", "other", "other"]
    assert {row["column"] for row in rows} == {"country", "clade"}


def test_no_collapse_when_unique_count_within_cap():
    df = pd.DataFrame({"country": ["Brazil", "Brazil", "Argentina"]})

    out, rows = collapse_trait_states(df, ["country"], max_states=3)

    assert out.equals(df)
    assert rows == []


def test_empty_and_na_values_do_not_count_as_states():
    df = pd.DataFrame({"trait": ["A", "A", "B", "C", "", "NA", "nan"]})

    out, rows = collapse_trait_states(df, ["trait"], max_states=2)

    assert out["trait"].tolist() == ["A", "A", "other", "other", "", "NA", "nan"]
    assert [row["state"] for row in rows] == ["B", "C"]
