"""Unit tests for the ViralQC skip-mode synthesizer."""

import csv
from pathlib import Path

import pytest

from flexpipe.ingest.synthesize_viralqc import (
    _iter_fasta_ids_and_seqlens,
    iter_fasta_ids,
    write_synthetic_viralqc_tsv,
)


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


# ── Internal helper: _iter_fasta_ids_and_seqlens ──────────────────────────────


class TestIterFastaIdsAndSeqlens:
    def test_returns_id_and_length_pairs(self, sample_fasta):
        pairs = _iter_fasta_ids_and_seqlens(str(sample_fasta))
        # sample_fasta has 3 sequences each 8 bp
        assert pairs == [("LOCAL001", 8), ("LOCAL002", 8), ("LOCAL003", 8)]

    def test_empty_fasta_returns_empty(self, tmp_path):
        f = tmp_path / "empty.fasta"
        f.write_text("")
        assert _iter_fasta_ids_and_seqlens(str(f)) == []

    def test_multiline_sequence_sums_lengths(self, tmp_path):
        f = tmp_path / "multi.fasta"
        f.write_text(">SEQ1\nAAAA\nCCCC\n>SEQ2\nGGGG\n")
        pairs = _iter_fasta_ids_and_seqlens(str(f))
        assert pairs == [("SEQ1", 8), ("SEQ2", 4)]

    def test_iter_fasta_ids_still_works(self, sample_fasta):
        """iter_fasta_ids should remain backward-compatible."""
        ids = iter_fasta_ids(str(sample_fasta))
        assert ids == ["LOCAL001", "LOCAL002", "LOCAL003"]


# ── Length-based coverage (genome_size > 0) ───────────────────────────────────


@pytest.fixture()
def length_fasta(tmp_path) -> Path:
    """Three sequences: 8 bp, 4 bp, 16 bp."""
    fasta = tmp_path / "varied.fasta"
    fasta.write_text(
        ">FULL\nATGCATGC\n"  # 8 bp
        ">HALF\nATGC\n"  # 4 bp
        ">DOUBLE\nATGCATGCATGCATGC\n"  # 16 bp
    )
    return fasta


class TestLengthBasedCoverage:
    def _read_coverage(self, tsv_path: Path) -> dict[str, float]:
        with open(tsv_path, newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            return {row["seqName"]: float(row["coverage"]) for row in reader}

    def test_genome_size_zero_all_coverage_one(self, tmp_path, length_fasta):
        """Default (genome_size=0) → all sequences get coverage 1.0 (backward compat)."""
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(length_fasta), str(out))  # genome_size defaults to 0
        cov = self._read_coverage(out)
        assert all(v == 1.0 for v in cov.values())

    def test_genome_size_zero_explicit(self, tmp_path, length_fasta):
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(length_fasta), str(out), genome_size=0)
        cov = self._read_coverage(out)
        assert all(v == 1.0 for v in cov.values())

    def test_full_length_sequence_coverage_one(self, tmp_path, length_fasta):
        """Sequence exactly genome_size bp long → coverage 1.0."""
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(length_fasta), str(out), genome_size=8)
        cov = self._read_coverage(out)
        assert cov["FULL"] == 1.0

    def test_half_length_sequence_coverage_half(self, tmp_path, length_fasta):
        """Sequence half the genome_size → coverage 0.5."""
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(length_fasta), str(out), genome_size=8)
        cov = self._read_coverage(out)
        assert cov["HALF"] == 0.5

    def test_overlength_sequence_capped_at_one(self, tmp_path, length_fasta):
        """Sequence longer than genome_size → coverage capped at 1.0."""
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(length_fasta), str(out), genome_size=8)
        cov = self._read_coverage(out)
        assert cov["DOUBLE"] == 1.0

    def test_coverage_four_decimal_places(self, tmp_path):
        """Coverage values are rounded to 4 decimal places."""
        fasta = tmp_path / "s.fasta"
        fasta.write_text(">S1\nATGC\n")  # 4 bp
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(fasta), str(out), genome_size=3)
        cov = self._read_coverage(out)
        # 4/3 ≈ 1.3333... capped at 1.0
        assert cov["S1"] == 1.0

    def test_partial_coverage_rounded(self, tmp_path):
        """1/3 → 0.3333."""
        fasta = tmp_path / "s.fasta"
        fasta.write_text(">S1\nATG\n")  # 3 bp
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(fasta), str(out), genome_size=9)
        cov = self._read_coverage(out)
        assert cov["S1"] == pytest.approx(1 / 3, abs=1e-4)

    def test_genome_quality_still_a_with_genome_size(self, tmp_path, length_fasta):
        """genome_size does not change genomeQuality — still A."""
        out = tmp_path / "r.tsv"
        write_synthetic_viralqc_tsv(str(length_fasta), str(out), genome_size=8)
        with open(out, newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                assert row["genomeQuality"] == "A"
                assert row["qc.overallStatus"] == "good"
