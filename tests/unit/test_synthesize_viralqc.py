"""Unit tests for the ViralQC skip-mode synthesizer."""

import csv
from pathlib import Path

import pytest

from flexpipe.ingest.synthesize_viralqc import iter_fasta_ids, write_synthetic_viralqc_tsv


@pytest.fixture()
def sample_fasta(tmp_path) -> Path:
    fasta = tmp_path / "seqs.fasta"
    fasta.write_text(
        ">LOCAL001 extra header text\n"
        "ATGCATGC\n"
        ">LOCAL002\n"
        "GCATGCAT\n"
        ">LOCAL003\n"
        "TTTTAAAA\n"
    )
    return fasta


class TestIterFastaIds:
    def test_returns_ids_without_description(self, sample_fasta):
        ids = iter_fasta_ids(str(sample_fasta))
        assert ids == ["LOCAL001", "LOCAL002", "LOCAL003"]

    def test_empty_fasta_returns_empty_list(self, tmp_path):
        empty = tmp_path / "empty.fasta"
        empty.write_text("")
        assert iter_fasta_ids(str(empty)) == []

    def test_skips_non_header_lines(self, sample_fasta):
        ids = iter_fasta_ids(str(sample_fasta))
        assert "ATGCATGC" not in ids
        assert "extra" not in ids

    def test_header_with_pipe_delimiter(self, tmp_path):
        """Sequence IDs with pipe delimiters common in NCBI records."""
        fasta = tmp_path / "ncbi.fasta"
        fasta.write_text(">LC123|extra\nATGC\n>MK456|other\nGCTA\n")
        ids = iter_fasta_ids(str(fasta))
        assert ids == ["LC123|extra", "MK456|other"]


class TestWriteSyntheticViralqcTsv:
    def test_output_file_is_created(self, tmp_path, sample_fasta):
        out = tmp_path / "results" / "results.tsv"
        write_synthetic_viralqc_tsv(str(sample_fasta), str(out))
        assert out.exists()

    def test_parent_directories_created(self, tmp_path, sample_fasta):
        out = tmp_path / "deep" / "nested" / "results.tsv"
        write_synthetic_viralqc_tsv(str(sample_fasta), str(out))
        assert out.exists()

    def test_header_row(self, tmp_path, sample_fasta):
        out = tmp_path / "results.tsv"
        write_synthetic_viralqc_tsv(str(sample_fasta), str(out))
        with open(out, newline="") as fh:
            reader = csv.reader(fh, delimiter="\t")
            header = next(reader)
        assert header == ["seqName", "genomeQuality", "coverage", "qc.overallStatus"]

    def test_one_row_per_sequence(self, tmp_path, sample_fasta):
        out = tmp_path / "results.tsv"
        write_synthetic_viralqc_tsv(str(sample_fasta), str(out))
        with open(out, newline="") as fh:
            rows = list(csv.reader(fh, delimiter="\t"))
        assert len(rows) == 4  # 1 header + 3 sequences

    def test_all_rows_have_grade_a(self, tmp_path, sample_fasta):
        out = tmp_path / "results.tsv"
        write_synthetic_viralqc_tsv(str(sample_fasta), str(out))
        with open(out, newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            rows = list(reader)
        for row in rows:
            assert row["genomeQuality"] == "A"
            assert row["qc.overallStatus"] == "good"

    def test_seq_names_match_fasta_ids(self, tmp_path, sample_fasta):
        out = tmp_path / "results.tsv"
        write_synthetic_viralqc_tsv(str(sample_fasta), str(out))
        with open(out, newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            names = [row["seqName"] for row in reader]
        assert names == ["LOCAL001", "LOCAL002", "LOCAL003"]
