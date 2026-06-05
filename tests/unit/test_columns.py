"""Unit tests for flexpipe.curate.columns — harmonize and drop."""

import pandas as pd

from flexpipe.curate.columns import (
    DROP,
    apply_harmonization,
    drop_columns,
    harmonize_column,
)


class TestHarmonizeColumn:
    """Tests for ``harmonize_column(df, src, dst)``."""

    def test_fills_empty_dst_from_src(self):
        df = pd.DataFrame(
            {
                "hostNameCommon": ["Homo sapiens", "Sus scrofa"],
                "host": ["", ""],
            }
        )
        result = harmonize_column(df, "hostNameCommon", "host")
        assert list(result["host"]) == ["Homo sapiens", "Sus scrofa"]
        assert "hostNameCommon" not in result.columns

    def test_existing_dst_not_overwritten(self):
        """Non-empty dst values must NOT be overridden by src."""
        df = pd.DataFrame(
            {
                "hostNameCommon": ["Homo sapiens", "Sus scrofa"],
                "host": ["human", ""],
            }
        )
        result = harmonize_column(df, "hostNameCommon", "host")
        assert result["host"].tolist() == ["human", "Sus scrofa"]

    def test_missing_src_is_noop(self):
        """If src column does not exist, return df unchanged."""
        df = pd.DataFrame({"host": ["human"]})
        result = harmonize_column(df, "missingCol", "host")
        assert list(result.columns) == ["host"]

    def test_missing_dst_created(self):
        """If dst column does not exist, it is created from src."""
        df = pd.DataFrame({"hostNameCommon": ["human", ""]})
        result = harmonize_column(df, "hostNameCommon", "host")
        assert "host" in result.columns
        assert result["host"].tolist() == ["human", ""]
        assert "hostNameCommon" not in result.columns

    def test_whitespace_only_dst_treated_as_empty(self):
        df = pd.DataFrame({"src": ["filled"], "dst": ["   "]})
        result = harmonize_column(df, "src", "dst")
        assert result["dst"].tolist() == ["filled"]

    def test_src_dropped_after_merge(self):
        df = pd.DataFrame({"src": ["x"], "dst": ["y"]})
        result = harmonize_column(df, "src", "dst")
        assert "src" not in result.columns


class TestApplyHarmonization:
    """Tests for ``apply_harmonization`` — applies all HARMONIZE_PAIRS."""

    def test_host_name_common_merged(self):
        df = pd.DataFrame(
            {
                "hostNameCommon": ["Homo sapiens"],
                "strain": ["SEQ001"],
            }
        )
        result = apply_harmonization(df)
        assert "host" in result.columns
        assert "hostNameCommon" not in result.columns
        assert result["host"].tolist() == ["Homo sapiens"]

    def test_sample_id_from_specimen_collector(self):
        df = pd.DataFrame(
            {
                "specimenCollectorSampleId": ["ABC-123"],
                "strain": ["SEQ001"],
            }
        )
        result = apply_harmonization(df)
        assert "sample_id" in result.columns
        assert result["sample_id"].tolist() == ["ABC-123"]

    def test_idempotent_when_columns_absent(self):
        """Columns that are not present are silently skipped."""
        df = pd.DataFrame({"strain": ["SEQ001"], "date": ["2024-01-01"]})
        result = apply_harmonization(df)
        # Should have at most the input columns (no crashes)
        assert "strain" in result.columns


class TestDropColumns:
    """Tests for ``drop_columns``."""

    def test_drops_known_columns(self):
        drop_sample = {"submissionId", "isRevocation", "version"}
        df = pd.DataFrame({col: ["x"] for col in drop_sample} | {"strain": ["SEQ001"]})
        result = drop_columns(df, drop_set=drop_sample)
        assert "strain" in result.columns
        for col in drop_sample:
            assert col not in result.columns

    def test_ignores_absent_columns(self):
        """drop_columns must not raise if a column in drop_set is absent."""
        df = pd.DataFrame({"strain": ["SEQ001"]})
        result = drop_columns(df, drop_set={"nonExistentColumn"})
        assert "strain" in result.columns

    def test_full_drop_set_leaves_required_columns(self):
        """Using the full DROP set must not remove key pipeline columns."""
        cols_to_keep = {"strain", "date", "country", "division", "clade", "source"}
        df = pd.DataFrame({col: ["x"] for col in cols_to_keep | DROP})
        result = drop_columns(df)
        for col in cols_to_keep:
            assert col in result.columns, f"Required column dropped: {col}"

    def test_drop_set_is_complete_no_pipeline_columns(self):
        """Sanity check: critical pipeline columns must NOT be in DROP."""
        pipeline_columns = {
            "strain",
            "date",
            "country",
            "division",
            "location",
            "clade",
            "clade_truncated",
            "region",
            "source",
            "data_use",
            "host",
            "genome_quality",
            "coverage",
        }
        accidentally_dropped = pipeline_columns & DROP
        assert (
            accidentally_dropped == set()
        ), f"Critical pipeline columns found in DROP: {accidentally_dropped}"
