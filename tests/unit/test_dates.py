"""Unit tests for flexible pre-Augur date normalization."""

import pandas as pd

from flexpipe.curate.dates import load_date_policy, normalize_date, normalize_dates_table


def test_normalizes_year_month_and_full_date_forms():
    policy = load_date_policy()

    assert normalize_date("2024", policy).value == "2024"
    assert normalize_date("2024/03", policy).value == "2024-03"
    assert normalize_date("Mar-2024", policy).value == "2024-03"
    assert normalize_date("2024/03/07", policy).value == "2024-03-07"
    assert normalize_date("07-Mar-2024", policy).value == "2024-03-07"


def test_slash_dates_follow_policy_and_log_ambiguity():
    policy = load_date_policy()

    result = normalize_date("03/04/2024", policy)

    assert result.value == "2024-03-04"
    assert result.status == "ambiguous"
    assert "MDY" in result.reason


def test_impossible_and_missing_dates_become_empty():
    policy = load_date_policy()

    assert normalize_date("2024-02-31", policy).status == "invalid"
    assert normalize_date("2024-02-31", policy).value == ""
    assert normalize_date("unknown", policy).status == "missing"
    assert normalize_date("missing: synthetic construct", policy).status == "missing"


def test_normalize_dates_table_logs_changed_and_broken_rows():
    policy = load_date_policy()
    df = pd.DataFrame({"strain": ["a", "b", "c"], "date": ["2024/03/07", "bad", "2024"]})

    out, rows = normalize_dates_table(df, date_field="date", policy=policy)

    assert out["date"].tolist() == ["2024-03-07", "", "2024"]
    assert {row["status"] for row in rows} == {"normalized", "invalid"}
    assert any(row["original"] == "bad" and row["normalized"] == "" for row in rows)
