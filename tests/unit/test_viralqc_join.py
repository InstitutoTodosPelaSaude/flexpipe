"""Unit tests for flexpipe.curate.viralqc_join.join_viralqc."""

import os
import tempfile

import pandas as pd
import pytest

from flexpipe.curate.viralqc_join import join_viralqc


def _make_metadata(*strains):
    """Minimal metadata DataFrame with a strain column."""
    return pd.DataFrame({"strain": list(strains), "date": ["2024-01-01"] * len(strains)})


def _write_viralqc(tmp_path, rows):
    """Write a mock ViralQC TSV file and return its path."""
    df = pd.DataFrame(rows)
    path = tmp_path / "viralqc_results.tsv"
    df.to_csv(path, sep="\t", index=False)
    return str(path)


class TestJoinViralqcNoFile:
    """Behaviour when ViralQC file is absent or None."""

    def test_none_path_adds_placeholder_columns(self):
        df = _make_metadata("SEQ001")
        result = join_viralqc(df, nextclade_path=None, viralqc_cfg={})
        assert "genome_quality" in result.columns
        assert "qc_overall_status" in result.columns
        assert "coverage" in result.columns

    def test_missing_file_adds_placeholder_columns(self, tmp_path):
        df = _make_metadata("SEQ001")
        result = join_viralqc(df, nextclade_path=str(tmp_path / "missing.tsv"), viralqc_cfg={})
        assert "genome_quality" in result.columns

    def test_placeholder_genome_quality_is_empty(self):
        df = _make_metadata("SEQ001")
        result = join_viralqc(df, nextclade_path=None, viralqc_cfg={})
        assert result["genome_quality"].tolist() == [""]


class TestJoinViralqcClade:
    """Clade column merging rules."""

    def test_viralqc_clade_overrides_empty_existing(self, tmp_path):
        df = _make_metadata("SEQ001")
        df["clade"] = ""
        path = _write_viralqc(tmp_path, [{"seqName": "SEQ001", "clade": "I.A", "genomeQuality": "A"}])
        result = join_viralqc(df, path, {"clade_column": "clade"})
        assert result.loc[0, "clade"] == "I.A"

    def test_viralqc_clade_overrides_existing_non_empty(self, tmp_path):
        """ViralQC result replaces any existing clade value when non-empty."""
        df = _make_metadata("SEQ001")
        df["clade"] = "OLD_CLADE"
        path = _write_viralqc(tmp_path, [{"seqName": "SEQ001", "clade": "I.B", "genomeQuality": "A"}])
        result = join_viralqc(df, path, {"clade_column": "clade"})
        assert result.loc[0, "clade"] == "I.B"

    def test_empty_viralqc_clade_keeps_existing(self, tmp_path):
        """If ViralQC assigns no clade (empty string), the existing clade is preserved."""
        df = _make_metadata("SEQ001")
        df["clade"] = "EXISTING"
        path = _write_viralqc(tmp_path, [{"seqName": "SEQ001", "clade": "", "genomeQuality": "A"}])
        result = join_viralqc(df, path, {"clade_column": "clade"})
        assert result.loc[0, "clade"] == "EXISTING"

    def test_no_viralqc_match_keeps_existing(self, tmp_path):
        """Sequences with no ViralQC row (left-join) keep their original clade."""
        df = _make_metadata("SEQ001", "SEQ002")
        df["clade"] = ["CLADE_A", "CLADE_B"]
        # Only SEQ001 in ViralQC
        path = _write_viralqc(tmp_path, [{"seqName": "SEQ001", "clade": "NEW", "genomeQuality": "A"}])
        result = join_viralqc(df, path, {"clade_column": "clade"})
        assert result.loc[result["strain"] == "SEQ002", "clade"].iloc[0] == "CLADE_B"


class TestJoinViralqcQuality:
    """Genome quality and coverage columns."""

    def test_genome_quality_set(self, tmp_path):
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [{"seqName": "SEQ001", "genomeQuality": "B", "clade": "I"}])
        result = join_viralqc(df, path, {})
        assert result.loc[0, "genome_quality"] == "B"

    def test_coverage_from_nc_coverage(self, tmp_path):
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [{"seqName": "SEQ001", "coverage": "0.97", "genomeQuality": "A"}])
        result = join_viralqc(df, path, {})
        assert abs(float(result.loc[0, "coverage"]) - 0.97) < 1e-6

    def test_qc_overall_status_mapped(self, tmp_path):
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [{
            "seqName": "SEQ001",
            "genomeQuality": "A",
            "qc.overallStatus": "good",
        }])
        result = join_viralqc(df, path, {})
        assert result.loc[0, "qc_overall_status"] == "good"


class TestJoinViralqcContamination:
    """Virus / segment cross-contamination filtering."""

    def test_wrong_virus_flagged_D(self, tmp_path):
        df = _make_metadata("SEQ001", "SEQ002")
        path = _write_viralqc(tmp_path, [
            {"seqName": "SEQ001", "virus": "YFV", "genomeQuality": "A"},
            {"seqName": "SEQ002", "virus": "DENV", "genomeQuality": "A"},
        ])
        cfg = {"expected_virus": "YFV"}
        result = join_viralqc(df, path, cfg)
        assert result.loc[result["strain"] == "SEQ001", "genome_quality"].iloc[0] == "A"
        assert result.loc[result["strain"] == "SEQ002", "genome_quality"].iloc[0] == "D"

    def test_unclassified_virus_flagged_D(self, tmp_path):
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [
            {"seqName": "SEQ001", "virus": "unclassified virus", "genomeQuality": "A"},
        ])
        cfg = {"expected_virus": "YFV"}
        result = join_viralqc(df, path, cfg)
        assert result.loc[0, "genome_quality"] == "D"

    def test_correct_virus_not_flagged(self, tmp_path):
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [
            {"seqName": "SEQ001", "virus": "YFV", "genomeQuality": "A"},
        ])
        cfg = {"expected_virus": "YFV"}
        result = join_viralqc(df, path, cfg)
        assert result.loc[0, "genome_quality"] == "A"

    def test_wrong_segment_flagged_D(self, tmp_path):
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [
            {"seqName": "SEQ001", "segment": "N", "genomeQuality": "A"},
        ])
        cfg = {"expected_segment": "L"}
        result = join_viralqc(df, path, cfg)
        assert result.loc[0, "genome_quality"] == "D"

    def test_empty_virus_not_excluded(self, tmp_path):
        """Sequences not analyzed by ViralQC (empty virus) must not be flagged."""
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [
            {"seqName": "SEQ001", "virus": "", "genomeQuality": "A"},
        ])
        cfg = {"expected_virus": "YFV"}
        result = join_viralqc(df, path, cfg)
        assert result.loc[0, "genome_quality"] == "A"

    def test_no_seqname_column_skips_join(self, tmp_path):
        """ViralQC file without 'seqName' is silently ignored."""
        df = _make_metadata("SEQ001")
        path = _write_viralqc(tmp_path, [{"name": "SEQ001", "genomeQuality": "A"}])
        result = join_viralqc(df, path, {})
        assert result.loc[0, "genome_quality"] == ""
