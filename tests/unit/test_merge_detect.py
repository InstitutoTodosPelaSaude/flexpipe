"""Unit tests for flexpipe.ingest.merge — format detection and FASTA-authority logic."""

import io
import os
import textwrap

import pandas as pd
import pytest

from flexpipe.ingest.merge import (
    detect_id_column,
    read_fasta_ids,
    read_fasta_records,
    read_itps_tsv_metadata,
    read_local_metadata,
    read_xlsx_metadata,
)


# ── FASTA helpers ──────────────────────────────────────────────────────────────


def _write_fasta(path, records):
    """Write ``{id: seq}`` dict to a FASTA file."""
    with open(path, "w") as fh:
        for seq_id, seq in records.items():
            fh.write(f">{seq_id}\n{seq}\n")


class TestReadFastaIds:
    def test_reads_ids(self, tmp_path):
        fasta = tmp_path / "seqs.fasta"
        _write_fasta(fasta, {"SEQ001": "ACGT", "SEQ002": "TTTT"})
        ids = read_fasta_ids(str(fasta))
        assert ids == {"SEQ001", "SEQ002"}

    def test_trims_description(self, tmp_path):
        """Only the first whitespace-delimited token is used as the ID."""
        fasta = tmp_path / "seqs.fasta"
        with open(fasta, "w") as fh:
            fh.write(">SEQ001 some description\nACGT\n")
        ids = read_fasta_ids(str(fasta))
        assert "SEQ001" in ids
        assert "SEQ001 some description" not in ids


class TestReadFastaRecords:
    def test_reads_records(self, tmp_path):
        fasta = tmp_path / "seqs.fasta"
        _write_fasta(fasta, {"SEQ001": "ACGT", "SEQ002": "TTTTGGGG"})
        records = read_fasta_records(str(fasta))
        assert records["SEQ001"] == "ACGT"
        assert records["SEQ002"] == "TTTTGGGG"

    def test_deduplicates_ids(self, tmp_path):
        """First occurrence of duplicate ID wins."""
        fasta = tmp_path / "seqs.fasta"
        with open(fasta, "w") as fh:
            fh.write(">SEQ001\nAAAA\n>SEQ001\nTTTT\n")
        records = read_fasta_records(str(fasta))
        assert records["SEQ001"] == "AAAA"


# ── TSV/XLSX format detection ──────────────────────────────────────────────────


class TestDetectIdColumn:
    def test_finds_accession_version(self):
        df = pd.DataFrame({"accessionVersion": ["X"], "date": ["2024"]})
        assert detect_id_column(df) == "accessionVersion"

    def test_finds_strain(self):
        df = pd.DataFrame({"strain": ["X"], "date": ["2024"]})
        assert detect_id_column(df) == "strain"

    def test_accession_preferred_over_strain(self):
        df = pd.DataFrame({"accessionVersion": ["X"], "strain": ["Y"]})
        assert detect_id_column(df) == "accessionVersion"

    def test_raises_if_neither(self):
        df = pd.DataFrame({"other": ["X"]})
        with pytest.raises(ValueError):
            detect_id_column(df)


class TestReadItpsTsvMetadata:
    """Tests for ITpS new TSV format (PascalCase headers, 'ID' column)."""

    def _write_itps_tsv(self, tmp_path, rows=None):
        rows = rows or [
            {"ID": "ITPS001", "CollectionDate": "2024-01-01", "Country": "Brazil",
             "State": "Espírito Santo", "City": "Serra", "HostSpecies": "Homo sapiens",
             "DataUse": "open"},
        ]
        df = pd.DataFrame(rows)
        path = tmp_path / "itps_new.tsv"
        df.to_csv(path, sep="\t", index=False)
        return path

    def test_id_renamed_to_accession_version(self, tmp_path):
        path = self._write_itps_tsv(tmp_path)
        result = read_itps_tsv_metadata(str(path))
        assert "accessionVersion" in result.columns
        assert "ID" not in result.columns

    def test_source_is_itps(self, tmp_path):
        path = self._write_itps_tsv(tmp_path)
        result = read_itps_tsv_metadata(str(path))
        assert result["source"].tolist() == ["ITpS"]

    def test_data_use_uppercased(self, tmp_path):
        path = self._write_itps_tsv(tmp_path)
        result = read_itps_tsv_metadata(str(path))
        assert result["dataUseTerms"].tolist() == ["OPEN"]

    def test_vqc_columns_stripped(self, tmp_path):
        """ViralQC output columns in the ITpS TSV must be removed."""
        rows = [{"ID": "ITPS001", "GenomeQuality": "A", "Coverage": "0.97"}]
        df = pd.DataFrame(rows)
        path = tmp_path / "itps_vqc.tsv"
        df.to_csv(path, sep="\t", index=False)
        result = read_itps_tsv_metadata(str(path))
        assert "GenomeQuality" not in result.columns
        assert "Coverage" not in result.columns

    def test_pascal_to_ppx_renaming(self, tmp_path):
        path = self._write_itps_tsv(tmp_path)
        result = read_itps_tsv_metadata(str(path))
        # CollectionDate → sampleCollectionDate
        assert "sampleCollectionDate" in result.columns
        # Country → geoLocCountry
        assert "geoLocCountry" in result.columns


class TestReadLocalMetadata:
    """Format auto-detection in ``read_local_metadata``."""

    def _write_itps_tsv(self, tmp_path):
        df = pd.DataFrame([
            {"ID": "ITPS001", "CollectionDate": "2024-01-01", "Country": "Brazil"},
        ])
        path = tmp_path / "itps.tsv"
        df.to_csv(path, sep="\t", index=False)
        return path

    def _write_ppx_tsv(self, tmp_path):
        df = pd.DataFrame([
            {"accessionVersion": "PPX001", "date": "2024-01-01", "country": "Brazil"},
        ])
        path = tmp_path / "ppx.tsv"
        df.to_csv(path, sep="\t", index=False)
        return path

    def test_detects_itps_tsv_by_id_column(self, tmp_path):
        path = self._write_itps_tsv(tmp_path)
        result = read_local_metadata(str(path))
        assert "accessionVersion" in result.columns  # was 'ID'
        assert "source" in result.columns
        assert result["source"].iloc[0] == "ITpS"

    def test_detects_ppx_tsv_as_passthrough(self, tmp_path):
        path = self._write_ppx_tsv(tmp_path)
        result = read_local_metadata(str(path))
        assert "accessionVersion" in result.columns

    def test_data_use_uppercased_in_passthrough(self, tmp_path):
        df = pd.DataFrame([
            {"accessionVersion": "PPX001", "dataUseTerms": "open"},
        ])
        path = tmp_path / "ppx.tsv"
        df.to_csv(path, sep="\t", index=False)
        result = read_local_metadata(str(path))
        assert result["dataUseTerms"].iloc[0] == "OPEN"
