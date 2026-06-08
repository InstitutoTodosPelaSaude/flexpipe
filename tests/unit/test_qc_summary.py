"""Unit tests for flexpipe.curate.qc_summary — QC report builder."""

import json

import pandas as pd
import pytest

from flexpipe.curate.qc_summary import build_qc_report, write_qc_artifacts

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_curated(path, rows):
    """Write a curated_metadata.tsv fixture with given rows."""
    df = pd.DataFrame(rows)
    path.mkdir(parents=True, exist_ok=True)
    tsv = path / "curated_metadata.tsv"
    df.to_csv(tsv, sep="\t", index=False)
    return tsv


def _write_filter_log(path, rows):
    """Write a filter_log.tsv fixture (always writes a proper header)."""
    cols = ["strain", "filter", "kwargs"]
    df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    tsv = path / "filter_log.tsv"
    df.to_csv(tsv, sep="\t", index=False)
    return tsv


def _write_final(path, rows):
    """Write a final_metadata.tsv fixture."""
    df = pd.DataFrame(rows)
    tsv = path / "final_metadata.tsv"
    df.to_csv(tsv, sep="\t", index=False)
    return tsv


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildQcReport:
    def test_totals(self, tmp_path):
        curated_rows = [
            {"strain": "s1", "genome_quality": "A", "coverage": 0.95},
            {"strain": "s2", "genome_quality": "B", "coverage": 0.80},
            {"strain": "s3", "genome_quality": "C", "coverage": 0.72},
            {"strain": "s4", "genome_quality": "D", "coverage": 0.40},
        ]
        final_rows = [
            {"strain": "s1"},
            {"strain": "s2"},
        ]
        filter_rows = [
            {"strain": "s3", "filter": "exclude_by_query", "kwargs": "{}"},
            {"strain": "s4", "filter": "filter_by_exclude_where", "kwargs": "{}"},
        ]
        curated = _write_curated(tmp_path, curated_rows)
        filter_log = _write_filter_log(tmp_path, filter_rows)
        final = _write_final(tmp_path, final_rows)

        report = build_qc_report(curated, filter_log, final)

        assert report["total_curated"] == 4
        assert report["total_retained"] == 2
        assert report["total_excluded"] == 2

    def test_genome_quality_counts(self, tmp_path):
        curated_rows = [
            {"strain": "s1", "genome_quality": "A", "coverage": 0.95},
            {"strain": "s2", "genome_quality": "A", "coverage": 0.90},
            {"strain": "s3", "genome_quality": "B", "coverage": 0.80},
            {"strain": "s4", "genome_quality": "D", "coverage": 0.30},
            {"strain": "s5", "genome_quality": "", "coverage": 0.00},
        ]
        curated = _write_curated(tmp_path, curated_rows)
        filter_log = _write_filter_log(tmp_path, [])
        final = _write_final(tmp_path, [{"strain": "s1"}, {"strain": "s2"}, {"strain": "s3"}])

        report = build_qc_report(curated, filter_log, final)
        gq = report["genome_quality_counts"]

        assert gq["A"] == 2
        assert gq["B"] == 1
        assert gq["D"] == 1
        assert gq["(empty)"] == 1
        # Grade C was absent → count should be 0
        assert gq["C"] == 0

    def test_exclusion_by_filter(self, tmp_path):
        curated_rows = [
            {"strain": f"s{i}", "genome_quality": "A", "coverage": 0.90} for i in range(5)
        ]
        filter_rows = [
            {"strain": "s3", "filter": "filter_by_exclude_where", "kwargs": "{}"},
            {"strain": "s4", "filter": "exclude_by_query", "kwargs": "{}"},
        ]
        curated = _write_curated(tmp_path, curated_rows)
        filter_log = _write_filter_log(tmp_path, filter_rows)
        final = _write_final(tmp_path, [{"strain": "s0"}, {"strain": "s1"}, {"strain": "s2"}])

        report = build_qc_report(curated, filter_log, final)
        excl = report["exclusion_by_filter"]

        assert excl.get("filter_by_exclude_where") == 1
        assert excl.get("exclude_by_query") == 1

    def test_coverage_stats_populated(self, tmp_path):
        curated_rows = [
            {"strain": "s1", "genome_quality": "A", "coverage": "0.90"},
            {"strain": "s2", "genome_quality": "A", "coverage": "0.80"},
        ]
        curated = _write_curated(tmp_path, curated_rows)
        filter_log = _write_filter_log(tmp_path, [])
        final = _write_final(tmp_path, [{"strain": "s1"}, {"strain": "s2"}])

        report = build_qc_report(curated, filter_log, final)
        cov = report["coverage_stats"]

        assert "mean" in cov
        assert cov["mean"] == pytest.approx(0.85, rel=1e-3)
        assert cov["missing_count"] == 0

    def test_missing_filter_log_produces_empty_exclusion_reasons(self, tmp_path):
        """When filter_log.tsv does not exist, exclusion_by_filter is empty (not an error)."""
        curated_rows = [{"strain": "s1", "genome_quality": "A", "coverage": "0.95"}]
        curated = _write_curated(tmp_path, curated_rows)
        nonexistent_log = tmp_path / "nonexistent_filter_log.tsv"
        final = _write_final(tmp_path, [{"strain": "s1"}])

        report = build_qc_report(curated, nonexistent_log, final)
        assert report["exclusion_by_filter"] == {}

    def test_cross_contamination_count_uses_explicit_reasons(self, tmp_path):
        """cross_contamination_count only reflects wrong-virus/wrong-segment reasons."""
        curated_rows = [
            {"strain": "s1", "genome_quality": "A", "coverage": "0.95"},
            {
                "strain": "s2",
                "genome_quality": "D",
                "coverage": "0.50",
                "qc_exclusion_reason": "wrong_virus",
            },
            {
                "strain": "s3",
                "genome_quality": "D",
                "coverage": "0.45",
                "qc_exclusion_reason": "viralqc_quality",
            },
        ]
        curated = _write_curated(tmp_path, curated_rows)
        filter_log = _write_filter_log(tmp_path, [])
        final = _write_final(tmp_path, [{"strain": "s1"}])

        report = build_qc_report(curated, filter_log, final)
        assert report["cross_contamination_count"] == 1


class TestWriteQcArtifacts:
    def test_json_written(self, tmp_path):
        report = {
            "total_curated": 10,
            "total_retained": 8,
            "total_excluded": 2,
            "genome_quality_counts": {"A": 6, "B": 2, "C": 1, "D": 1, "(empty)": 0},
            "coverage_stats": {"mean": 0.88},
            "cross_contamination_count": 1,
            "exclusion_by_filter": {"filter_by_exclude_where": 2},
        }
        json_path = tmp_path / "qc_report.json"
        tsv_path = tmp_path / "qc_summary.tsv"
        write_qc_artifacts(report, json_path, tsv_path)

        assert json_path.exists()
        loaded = json.loads(json_path.read_text())
        assert loaded["total_curated"] == 10
        assert loaded["total_retained"] == 8

    def test_tsv_written_with_grade_rows(self, tmp_path):
        report = {
            "total_curated": 5,
            "total_retained": 3,
            "total_excluded": 2,
            "genome_quality_counts": {"A": 3, "B": 1, "C": 1, "D": 0, "(empty)": 0},
            "coverage_stats": {},
            "cross_contamination_count": 0,
            "exclusion_by_filter": {},
        }
        json_path = tmp_path / "qc_report.json"
        tsv_path = tmp_path / "qc_summary.tsv"
        write_qc_artifacts(report, json_path, tsv_path)

        assert tsv_path.exists()
        df = pd.read_csv(tsv_path, sep="\t")
        assert "genome_quality" in df.columns
        assert "count" in df.columns
        a_row = df[df["genome_quality"] == "A"]
        assert len(a_row) == 1
        assert int(a_row["count"].iloc[0]) == 3
