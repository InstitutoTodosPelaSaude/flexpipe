"""Unit tests for flexpipe.curate.clade_filter."""

import logging
import sys

import pandas as pd

from flexpipe.curate.clade_filter import filter_by_clade, main

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_df(clades: list[str]) -> pd.DataFrame:
    """Build a minimal metadata DataFrame with strain + clade_truncated columns."""
    return pd.DataFrame(
        {
            "strain": [f"SEQ{i:03d}" for i in range(len(clades))],
            "date": ["2024-01-01"] * len(clades),
            "clade_truncated": clades,
        }
    )


# ── Tests: disabled / pass-through ────────────────────────────────────────────


class TestPassThrough:
    def test_empty_column_returns_all_rows(self):
        df = _make_df(["B3", "D8", "B3.1"])
        kept, dropped = filter_by_clade(df, column="", include=[], exclude=[])
        assert len(kept) == 3
        assert dropped.empty

    def test_empty_column_kept_is_copy_not_same_object(self):
        df = _make_df(["B3"])
        kept, _ = filter_by_clade(df, column="", include=[], exclude=[])
        assert kept is not df  # must be a copy

    def test_missing_column_returns_all_rows_and_warns(self, caplog):
        df = _make_df(["B3", "D8"])
        with caplog.at_level(logging.WARNING, logger="flexpipe.curate.clade_filter"):
            kept, dropped = filter_by_clade(df, column="genotype", include=["B3"], exclude=[])
        assert len(kept) == 2
        assert dropped.empty
        assert "genotype" in caplog.text
        assert "not present in metadata" in caplog.text

    def test_no_include_no_exclude_passes_through(self):
        df = _make_df(["B3", "D8", "H1"])
        kept, dropped = filter_by_clade(df, column="clade_truncated", include=[], exclude=[])
        assert len(kept) == 3
        assert dropped.empty


# ── Tests: include (exact) ─────────────────────────────────────────────────────


class TestIncludeExact:
    def test_keeps_only_matching_rows(self):
        df = _make_df(["B3", "D8", "B3", "H1"])
        kept, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="exact"
        )
        assert list(kept["clade_truncated"]) == ["B3", "B3"]
        assert len(dropped) == 2

    def test_drop_reason_not_in_include(self):
        df = _make_df(["B3", "D8"])
        _, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="exact"
        )
        assert list(dropped["drop_reason"]) == ["not_in_include"]
        assert list(dropped["group_value"]) == ["D8"]

    def test_B3_does_not_match_B3_dot_1_exact(self):
        df = _make_df(["B3", "B3.1"])
        kept, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="exact"
        )
        # exact: "B3.1" != "B3" → dropped
        assert list(kept["clade_truncated"]) == ["B3"]
        assert len(dropped) == 1

    def test_multiple_includes(self):
        df = _make_df(["B3", "D8", "H1"])
        kept, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3", "D8"], exclude=[], match="exact"
        )
        assert len(kept) == 2
        assert len(dropped) == 1


# ── Tests: include (prefix) ────────────────────────────────────────────────────


class TestIncludePrefix:
    def test_prefix_keeps_B3_and_B3_dot_1(self):
        df = _make_df(["B3", "B3.1", "B3.2", "B30", "D8"])
        kept, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="prefix"
        )
        kept_values = list(kept["clade_truncated"])
        # B3, B3.1, B3.2 should be kept; B30 should not (dot-boundary)
        assert "B3" in kept_values
        assert "B3.1" in kept_values
        assert "B3.2" in kept_values
        assert "B30" not in kept_values
        assert "D8" not in kept_values

    def test_prefix_dot_boundary_B30_not_matched_by_B3(self):
        df = _make_df(["B30", "B3"])
        kept, _ = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="prefix"
        )
        assert list(kept["clade_truncated"]) == ["B3"]

    def test_ECSA_II_prefix_matches_subclades(self):
        df = _make_df(["ECSA-II", "ECSA-II.1", "ECSA-IIb", "IOL"])
        kept, _ = filter_by_clade(
            df, column="clade_truncated", include=["ECSA-II"], exclude=[], match="prefix"
        )
        kept_values = list(kept["clade_truncated"])
        assert "ECSA-II" in kept_values
        assert "ECSA-II.1" in kept_values
        assert "ECSA-IIb" not in kept_values  # no dot-separator
        assert "IOL" not in kept_values


# ── Tests: exclude ─────────────────────────────────────────────────────────────


class TestExclude:
    def test_exclude_drops_matching_rows(self):
        df = _make_df(["B3", "D8", "H1"])
        kept, dropped = filter_by_clade(
            df, column="clade_truncated", include=[], exclude=["D8"], match="exact"
        )
        assert list(kept["clade_truncated"]) == ["B3", "H1"]
        assert list(dropped["drop_reason"]) == ["in_exclude"]
        assert list(dropped["group_value"]) == ["D8"]

    def test_exclude_multiple(self):
        df = _make_df(["B3", "D8", "H1", "D4"])
        kept, dropped = filter_by_clade(
            df, column="clade_truncated", include=[], exclude=["D8", "D4"], match="exact"
        )
        assert len(kept) == 2
        assert len(dropped) == 2


# ── Tests: include + exclude combined ─────────────────────────────────────────


class TestCombined:
    def test_include_applied_before_exclude(self):
        """include B3, then exclude B3.1 — B3 survives, B3.1 and D8 dropped."""
        df = _make_df(["B3", "B3.1", "D8"])
        kept, dropped = filter_by_clade(
            df,
            column="clade_truncated",
            include=["B3", "B3.1"],
            exclude=["B3.1"],
            match="exact",
        )
        assert list(kept["clade_truncated"]) == ["B3"]
        assert len(dropped) == 2  # D8 (not_in_include) + B3.1 (in_exclude)
        reasons = set(dropped["drop_reason"])
        assert "not_in_include" in reasons
        assert "in_exclude" in reasons


# ── Tests: dropped_df columns ─────────────────────────────────────────────────


class TestDroppedColumns:
    def test_dropped_df_has_expected_columns(self):
        df = _make_df(["B3", "D8"])
        _, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="exact"
        )
        assert "strain" in dropped.columns
        assert "group_value" in dropped.columns
        assert "drop_reason" in dropped.columns

    def test_dropped_df_empty_has_columns(self):
        df = _make_df(["B3"])
        _, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="exact"
        )
        assert dropped.empty
        assert list(dropped.columns) == ["strain", "group_value", "drop_reason"]

    def test_group_value_matches_column_value(self):
        df = _make_df(["B3", "D8"])
        _, dropped = filter_by_clade(
            df, column="clade_truncated", include=["B3"], exclude=[], match="exact"
        )
        assert dropped.iloc[0]["group_value"] == "D8"
        assert dropped.iloc[0]["strain"] == "SEQ001"


# ── Tests: main() round-trip ──────────────────────────────────────────────────


class TestMainRoundTrip:
    def test_main_filters_and_writes_outputs(self, tmp_path):
        # Write a minimal config.yaml
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            "clade_filter:\n  column: clade_truncated\n  include: [B3]\n  match: exact\n",
            encoding="utf-8",
        )
        # Write metadata
        meta_path = tmp_path / "metadata.tsv"
        df = _make_df(["B3", "D8", "B3.1"])
        df.to_csv(meta_path, sep="\t", index=False)
        # Write sequences FASTA
        fasta_path = tmp_path / "sequences.fasta"
        fasta_path.write_text(">SEQ000\nATCG\n>SEQ001\nGCTA\n>SEQ002\nTTTT\n", encoding="utf-8")
        out_meta = tmp_path / "out_meta.tsv"
        out_seq = tmp_path / "out_seq.fasta"
        out_log = tmp_path / "log.tsv"

        sys.argv = [
            "flexpipe-filter-clade",
            "--config",
            str(cfg_path),
            "--metadata",
            str(meta_path),
            "--sequences",
            str(fasta_path),
            "--output-metadata",
            str(out_meta),
            "--output-sequences",
            str(out_seq),
            "--log",
            str(out_log),
        ]
        main()

        # Output metadata: only B3 row (SEQ000)
        result = pd.read_csv(out_meta, sep="\t", dtype=str)
        assert list(result["clade_truncated"]) == ["B3"]
        assert list(result["strain"]) == ["SEQ000"]

        # Output FASTA: only SEQ000
        fasta_content = out_seq.read_text()
        assert ">SEQ000" in fasta_content
        assert ">SEQ001" not in fasta_content

        # Log: SEQ001 (D8) and SEQ002 (B3.1) dropped
        log = pd.read_csv(out_log, sep="\t", dtype=str)
        assert len(log) == 2
        assert set(log["drop_reason"]) == {"not_in_include"}

    def test_main_pass_through_when_disabled(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("data_source: pathoplexus\n", encoding="utf-8")
        meta_path = tmp_path / "metadata.tsv"
        df = _make_df(["B3", "D8"])
        df.to_csv(meta_path, sep="\t", index=False)
        fasta_path = tmp_path / "sequences.fasta"
        fasta_path.write_text(">SEQ000\nATCG\n>SEQ001\nGCTA\n", encoding="utf-8")
        out_meta = tmp_path / "out_meta.tsv"
        out_seq = tmp_path / "out_seq.fasta"
        out_log = tmp_path / "log.tsv"

        sys.argv = [
            "flexpipe-filter-clade",
            "--config",
            str(cfg_path),
            "--metadata",
            str(meta_path),
            "--sequences",
            str(fasta_path),
            "--output-metadata",
            str(out_meta),
            "--output-sequences",
            str(out_seq),
            "--log",
            str(out_log),
        ]
        main()

        result = pd.read_csv(out_meta, sep="\t", dtype=str)
        assert len(result) == 2  # all passed through

        log = pd.read_csv(out_log, sep="\t", dtype=str)
        assert len(log) == 0  # nothing dropped

    def test_main_fasta_metadata_mismatch(self, tmp_path):
        """FASTA has extra sequences not in metadata — they are silently dropped."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            "clade_filter:\n  column: clade_truncated\n  include: [B3]\n  match: exact\n",
            encoding="utf-8",
        )
        meta_path = tmp_path / "metadata.tsv"
        df = _make_df(["B3"])  # only SEQ000
        df.to_csv(meta_path, sep="\t", index=False)
        fasta_path = tmp_path / "sequences.fasta"
        # FASTA has SEQ000 + extra SEQ999
        fasta_path.write_text(">SEQ000\nATCG\n>SEQ999\nGGGG\n", encoding="utf-8")
        out_meta = tmp_path / "out_meta.tsv"
        out_seq = tmp_path / "out_seq.fasta"
        out_log = tmp_path / "log.tsv"

        sys.argv = [
            "flexpipe-filter-clade",
            "--config",
            str(cfg_path),
            "--metadata",
            str(meta_path),
            "--sequences",
            str(fasta_path),
            "--output-metadata",
            str(out_meta),
            "--output-sequences",
            str(out_seq),
            "--log",
            str(out_log),
        ]
        main()  # must not raise

        fasta_content = out_seq.read_text()
        assert ">SEQ000" in fasta_content
        assert ">SEQ999" not in fasta_content
