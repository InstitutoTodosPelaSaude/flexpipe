"""Unit tests for flexpipe.validate — build configuration pre-run checker."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from flexpipe.validate import (
    _check_clades_tsv,
    _check_data_source_prerequisites,
    _check_mask_sites_file,
    _check_reference_gb,
    _check_subsample_yaml,
    _check_viralqc_aliases,
    validate_build,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))
    return path


def _build_dir(tmp: Path) -> Path:
    d = tmp / "build"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _minimal_config(build_dir: Path, **overrides) -> Path:
    """Write a minimal valid config.yaml to the build dir."""
    cfg: dict = {
        "data_source": "pathoplexus",
        "pathoplexus": {"organism": "test-pathogen"},
        "viralqc": {"expected_virus": "", "expected_segment": ""},
    }
    cfg.update(overrides)
    p = build_dir / "config.yaml"
    p.write_text(yaml.dump(cfg))
    return p


# ── _check_subsample_yaml ──────────────────────────────────────────────────────


class TestCheckSubsampleYaml:
    def test_passes_for_valid_samples_list_group_by(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        _write(
            build_dir / "subsample.yaml",
            """
            samples:
              all:
                group_by: [country, year]
            """,
        )
        errors, warnings = [], []
        _check_subsample_yaml(build_dir, errors, warnings)
        assert errors == []
        assert warnings == []

    def test_error_for_subsamples_key(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        _write(
            build_dir / "subsample.yaml",
            """
            subsamples:
              all:
                group_by: [country]
            """,
        )
        errors, warnings = [], []
        _check_subsample_yaml(build_dir, errors, warnings)
        assert any("subsamples" in e for e in errors)

    def test_error_for_string_group_by(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        _write(
            build_dir / "subsample.yaml",
            """
            samples:
              all:
                group_by: "country year"
            """,
        )
        errors, warnings = [], []
        _check_subsample_yaml(build_dir, errors, warnings)
        assert any("group_by" in e for e in errors)

    def test_error_when_missing(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        errors, warnings = [], []
        _check_subsample_yaml(build_dir, errors, warnings)
        assert any("subsample.yaml" in e for e in errors)

    def test_warns_for_double_quoted_query(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        # Single-quoted YAML wrapping preserves the embedded double-quotes in the parsed value.
        raw = (
            "samples:\n"
            "  all:\n"
            "    group_by: [country]\n"
            "    query: 'division != \"Unknown\"'\n"
        )
        (build_dir / "subsample.yaml").write_text(raw)
        errors, warnings = [], []
        _check_subsample_yaml(build_dir, errors, warnings)
        assert errors == []
        assert any("double-quotes" in w or "double-quote" in w for w in warnings)


# ── _check_reference_gb ────────────────────────────────────────────────────────


class TestCheckReferenceGb:
    def test_passes_for_real_reference(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        _write(build_dir / "reference.gb", "LOCUS X03700 10678 bp\n...")
        errors, warnings = [], []
        _check_reference_gb(build_dir, errors, warnings)
        assert errors == []
        assert warnings == []

    def test_warns_for_placeholder(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        _write(build_dir / "reference.gb", "LOCUS PLACEHOLDER 0 bp\n")
        errors, warnings = [], []
        _check_reference_gb(build_dir, errors, warnings)
        assert errors == []
        assert any("PLACEHOLDER" in w for w in warnings)

    def test_error_when_missing(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        errors, warnings = [], []
        _check_reference_gb(build_dir, errors, warnings)
        assert any("reference.gb" in e for e in errors)


# ── _check_clades_tsv ─────────────────────────────────────────────────────────


class TestCheckCladesTsv:
    def test_passes_for_non_empty_clades(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        _write(build_dir / "clades.tsv", "clade\tgene\tsite\talt\n1\tE\t1\tA\n")
        errors, warnings = [], []
        _check_clades_tsv(build_dir, errors, warnings)
        assert errors == []
        assert warnings == []

    def test_warns_for_header_only(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        _write(build_dir / "clades.tsv", "clade\tgene\tsite\talt\n")
        errors, warnings = [], []
        _check_clades_tsv(build_dir, errors, warnings)
        assert errors == []
        assert any("header-only" in w for w in warnings)

    def test_error_when_missing(self, tmp_path):
        build_dir = _build_dir(tmp_path)
        errors, warnings = [], []
        _check_clades_tsv(build_dir, errors, warnings)
        assert any("clades.tsv" in e for e in errors)


# ── _check_mask_sites_file ────────────────────────────────────────────────────


class TestCheckMaskSitesFile:
    def test_passes_when_not_set(self, tmp_path):
        errors, warnings = [], []
        _check_mask_sites_file({}, tmp_path, errors, warnings)
        assert errors == []

    def test_passes_for_existing_nonempty_bed(self, tmp_path):
        bed = tmp_path / "mask.bed"
        bed.write_text("chrVirus\t0\t142\n")
        cfg = {"parameters": {"mask_sites_file": str(bed)}}
        errors, warnings = [], []
        _check_mask_sites_file(cfg, tmp_path, errors, warnings)
        assert errors == []
        assert warnings == []

    def test_error_for_missing_bed(self, tmp_path):
        cfg = {"parameters": {"mask_sites_file": "/nonexistent/mask.bed"}}
        errors, warnings = [], []
        _check_mask_sites_file(cfg, tmp_path, errors, warnings)
        assert any("mask_sites_file" in e for e in errors)

    def test_warns_for_empty_bed(self, tmp_path):
        bed = tmp_path / "empty.bed"
        bed.write_text("")
        cfg = {"parameters": {"mask_sites_file": str(bed)}}
        errors, warnings = [], []
        _check_mask_sites_file(cfg, tmp_path, errors, warnings)
        assert errors == []
        assert any("empty" in w for w in warnings)


# ── _check_data_source_prerequisites ─────────────────────────────────────────


class TestCheckDataSourcePrerequisites:
    def test_passes_ppx_with_organism(self, tmp_path):
        cfg = {"data_source": "pathoplexus", "pathoplexus": {"organism": "yellow-fever"}}
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert errors == []

    def test_error_ppx_missing_organism(self, tmp_path):
        cfg = {"data_source": "pathoplexus", "pathoplexus": {}}
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert any("organism" in e for e in errors)

    def test_passes_ncbi_with_taxid_and_email_in_config(self, tmp_path):
        cfg = {
            "data_source": "ncbi",
            "ncbi": {"taxid": 11103, "email": "ops@example.org"},
        }
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert errors == []
        assert warnings == []

    def test_error_ncbi_missing_taxid(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NCBI_EMAIL", "ops@example.org")
        cfg = {"data_source": "ncbi", "ncbi": {"email": "ops@example.org"}}
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert any("taxid" in e for e in errors)

    def test_error_ncbi_no_email_at_all(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NCBI_EMAIL", raising=False)
        cfg = {"data_source": "ncbi", "ncbi": {"taxid": 11103}}
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert any("email" in e.lower() for e in errors)

    def test_warns_ncbi_email_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NCBI_EMAIL", "ops@example.org")
        cfg = {"data_source": "ncbi", "ncbi": {"taxid": 11103}}
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert errors == []
        assert any("NCBI_EMAIL" in w for w in warnings)

    def test_passes_local_with_existing_files(self, tmp_path):
        meta = tmp_path / "meta.tsv"
        seqs = tmp_path / "seqs.fasta"
        meta.write_text("strain\n")
        seqs.write_text(">seq1\nACGT\n")
        cfg = {
            "data_source": "local",
            "local": {"metadata": str(meta), "sequences": str(seqs)},
        }
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert errors == []

    def test_error_local_missing_metadata(self, tmp_path):
        seqs = tmp_path / "seqs.fasta"
        seqs.write_text(">seq1\nACGT\n")
        cfg = {
            "data_source": "local",
            "local": {"metadata": "/nonexistent/meta.tsv", "sequences": str(seqs)},
        }
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert any("metadata" in e for e in errors)

    def test_error_local_missing_sequences(self, tmp_path):
        meta = tmp_path / "meta.tsv"
        meta.write_text("strain\n")
        cfg = {
            "data_source": "local",
            "local": {"metadata": str(meta), "sequences": "/nonexistent/seqs.fasta"},
        }
        errors, warnings = [], []
        _check_data_source_prerequisites(cfg, tmp_path, errors, warnings)
        assert any("sequences" in e for e in errors)


# ── _check_viralqc_aliases ────────────────────────────────────────────────────


class TestCheckViralqcAliases:
    def test_passes_when_not_set(self):
        errors, warnings = [], []
        _check_viralqc_aliases({}, errors, warnings)
        assert errors == []

    def test_warns_for_skip_mode(self):
        cfg = {"viralqc": {"mode": "skip"}}
        errors, warnings = [], []
        _check_viralqc_aliases(cfg, errors, warnings)
        assert errors == []
        assert any("skip" in w for w in warnings)

    def test_warns_for_precomputed_mode(self):
        cfg = {"viralqc": {"mode": "precomputed"}}
        errors, warnings = [], []
        _check_viralqc_aliases(cfg, errors, warnings)
        assert errors == []
        assert any("precomputed" in w for w in warnings)

    def test_known_virus_alias_passes_no_warning(self):
        """'yellow_fever' is a known alias in the bundled aliases.yaml."""
        # Check whether it's in the registry; if not, it just warns (not errors).
        cfg = {"viralqc": {"expected_virus": "yellow_fever"}}
        errors, warnings = [], []
        _check_viralqc_aliases(cfg, errors, warnings)
        # Either found (no warning) or unknown alias (warning only, no error).
        assert errors == []

    def test_unknown_virus_alias_warns_not_errors(self):
        """An alias not in the registry should warn, not error — literal matching still works."""
        cfg = {"viralqc": {"expected_virus": "totally_unknown_virus_xyz_not_in_registry"}}
        errors, warnings = [], []
        _check_viralqc_aliases(cfg, errors, warnings)
        assert errors == []
        assert any("not in alias registry" in w or "literal matching" in w for w in warnings)

    def test_known_segment_alias_passes(self):
        """'L' is a known segment alias (OROV, Lassa)."""
        cfg = {"viralqc": {"expected_segment": "L"}}
        errors, warnings = [], []
        _check_viralqc_aliases(cfg, errors, warnings)
        assert errors == []


# ── validate_build (end-to-end) ───────────────────────────────────────────────


class TestValidateBuild:
    def _write_minimal_build(self, build_dir: Path) -> Path:
        """Write a minimal valid build directory with config.yaml."""
        build_dir.mkdir(parents=True, exist_ok=True)
        # subsample.yaml
        _write(
            build_dir / "subsample.yaml",
            """
            samples:
              all:
                group_by: [country, year]
            """,
        )
        # reference.gb (not a placeholder)
        _write(build_dir / "reference.gb", "LOCUS TEST 100 bp\n...")
        # clades.tsv (with one row to avoid warning)
        _write(build_dir / "clades.tsv", "clade\tgene\tsite\talt\n1\tE\t1\tA\n")
        # config.yaml
        cfg = {
            "data_source": "pathoplexus",
            "pathoplexus": {"organism": "test-pathogen"},
        }
        p = build_dir / "config.yaml"
        p.write_text(yaml.dump(cfg))
        return p

    def test_returns_zero_for_clean_build(self, tmp_path):
        config_path = self._write_minimal_build(tmp_path / "clean-build")
        rc = validate_build(config_path)
        assert rc == 0

    def test_returns_one_for_build_with_errors(self, tmp_path):
        build_dir = tmp_path / "broken-build"
        build_dir.mkdir(parents=True, exist_ok=True)
        _write(
            build_dir / "subsample.yaml",
            """
            samples:
              all:
                group_by: [country]
            """,
        )
        _write(build_dir / "reference.gb", "LOCUS TEST 100 bp\n...")
        _write(build_dir / "clades.tsv", "clade\tgene\tsite\talt\n1\tE\t1\tA\n")
        # config.yaml with data_source=pathoplexus but no organism
        cfg = {"data_source": "pathoplexus", "pathoplexus": {}}
        (build_dir / "config.yaml").write_text(yaml.dump(cfg))
        rc = validate_build(build_dir / "config.yaml")
        assert rc == 1

    def test_returns_zero_for_warnings_only(self, tmp_path):
        """Warnings should not fail the validator (exit code 0)."""
        build_dir = tmp_path / "warn-build"
        build_dir.mkdir(parents=True, exist_ok=True)
        _write(
            build_dir / "subsample.yaml",
            """
            samples:
              all:
                group_by: [country]
            """,
        )
        # PLACEHOLDER reference → warning only
        _write(build_dir / "reference.gb", "LOCUS PLACEHOLDER 0 bp\n")
        # header-only clades.tsv → warning only
        _write(build_dir / "clades.tsv", "clade\tgene\tsite\talt\n")
        cfg = {"data_source": "pathoplexus", "pathoplexus": {"organism": "test-pathogen"}}
        (build_dir / "config.yaml").write_text(yaml.dump(cfg))
        rc = validate_build(build_dir / "config.yaml")
        assert rc == 0

    def test_validates_yfv_brazil_config(self):
        """The committed YFV Brazil build must pass the validator."""
        yfv_config = Path(__file__).parent.parent.parent / "builds" / "yfv-brazil" / "config.yaml"
        if not yfv_config.exists():
            pytest.skip("yfv-brazil build not present")
        rc = validate_build(yfv_config)
        assert rc == 0, "yfv-brazil should pass flexpipe-validate-build with no errors"
