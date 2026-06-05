"""Unit tests for flexpipe.io — table loading and FASTA helpers."""

import pytest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from flexpipe.io import (
    load_table,
    load_tsv,
    read_fasta_ids,
    read_fasta_records,
    write_fasta,
)


class TestLoadTable:
    def test_tsv_loaded(self, tmp_path):
        f = tmp_path / "data.tsv"
        f.write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")
        df = load_table(f)
        assert list(df.columns) == ["a", "b"]
        assert len(df) == 2

    def test_csv_loaded(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        df = load_table(f)
        assert len(df) == 2

    def test_nan_filled_with_empty_string_by_default(self, tmp_path):
        f = tmp_path / "data.tsv"
        f.write_text("a\tb\n1\t\n", encoding="utf-8")
        df = load_table(f)
        assert df.iloc[0]["b"] == ""

    def test_unsupported_extension_raises(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            load_table(f)

    def test_dtype_str_keeps_leading_zeros(self, tmp_path):
        f = tmp_path / "data.tsv"
        f.write_text("code\n007\n042\n", encoding="utf-8")
        df = load_table(f, dtype="str")
        assert df["code"].tolist() == ["007", "042"]


class TestLoadTsv:
    def test_loads_tsv(self, tmp_path):
        f = tmp_path / "t.tsv"
        f.write_text("x\ty\nalpha\tbeta\n", encoding="utf-8")
        df = load_tsv(f)
        assert df.iloc[0]["x"] == "alpha"


class TestFastaHelpers:
    @pytest.fixture()
    def fasta_file(self, tmp_path):
        f = tmp_path / "seqs.fasta"
        f.write_text(">SEQ1\nACGT\n>SEQ2\nTTTT\n", encoding="utf-8")
        return f

    def test_read_fasta_ids(self, fasta_file):
        ids = read_fasta_ids(fasta_file)
        assert ids == {"SEQ1", "SEQ2"}

    def test_read_fasta_records_count(self, fasta_file):
        recs = read_fasta_records(fasta_file)
        assert len(recs) == 2

    def test_read_fasta_records_sequence(self, fasta_file):
        recs = read_fasta_records(fasta_file)
        by_id = {r.id: str(r.seq) for r in recs}
        assert by_id["SEQ1"] == "ACGT"

    def test_write_fasta_round_trip(self, tmp_path):
        records = [
            SeqRecord(Seq("AAAA"), id="R1", description=""),
            SeqRecord(Seq("CCCC"), id="R2", description=""),
        ]
        out = tmp_path / "out.fasta"
        write_fasta(records, out)
        ids = read_fasta_ids(out)
        assert ids == {"R1", "R2"}

    def test_write_fasta_creates_parent_dirs(self, tmp_path):
        records = [SeqRecord(Seq("ACGT"), id="X", description="")]
        deep = tmp_path / "a" / "b" / "c" / "seqs.fasta"
        write_fasta(records, deep)
        assert deep.exists()
