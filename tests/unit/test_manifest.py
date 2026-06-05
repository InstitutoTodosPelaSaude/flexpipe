"""Unit tests for flexpipe.manifest.Manifest."""

import json

import pandas as pd
import pytest

from flexpipe.manifest import BOUNDARY_REQUIRED_COLUMNS, Manifest


@pytest.fixture
def manifest():
    return Manifest(run_date="2025-06-01", build_name="yfv-brazil")


class TestManifestBasics:
    """Construction and basic properties."""

    def test_run_id_contains_build_and_date(self, manifest):
        assert "yfv-brazil" in manifest.run_id
        assert "2025-06-01" in manifest.run_id

    def test_run_id_stable(self, manifest):
        """Multiple calls to run_id must return the same value."""
        assert manifest.run_id == manifest.run_id

    def test_config_hash_unknown_when_no_config(self, manifest):
        assert manifest.config_hash == "unknown"

    def test_config_hash_computed_from_file(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("data_source: pathoplexus\n")
        m = Manifest(run_date="2025-01-01", build_name="test", config_path=cfg)
        assert len(m.config_hash) == 16  # 16-char hex digest
        assert m.config_hash != "unknown"

    def test_config_hash_differs_for_different_content(self, tmp_path):
        cfg1 = tmp_path / "a.yaml"
        cfg2 = tmp_path / "b.yaml"
        cfg1.write_text("data_source: pathoplexus\n")
        cfg2.write_text("data_source: ncbi\n")
        m1 = Manifest(run_date="2025-01-01", build_name="test", config_path=cfg1)
        m2 = Manifest(run_date="2025-01-01", build_name="test", config_path=cfg2)
        assert m1.config_hash != m2.config_hash


class TestManifestRecordCounts:
    """record_counts() accumulation."""

    def test_counts_stored(self, manifest):
        manifest.record_counts("fetched", 1469)
        manifest.record_counts("subsampled", 342)
        assert manifest.counts["fetched"] == 1469
        assert manifest.counts["subsampled"] == 342

    def test_later_stage_overwrites(self, manifest):
        manifest.record_counts("curated", 1400)
        manifest.record_counts("curated", 1350)
        assert manifest.counts["curated"] == 1350


class TestManifestSave:
    """save() writes valid JSON."""

    def test_save_creates_file(self, manifest, tmp_path):
        path = tmp_path / "manifest.json"
        manifest.save(path)
        assert path.exists()

    def test_saved_json_is_valid(self, manifest, tmp_path):
        path = tmp_path / "manifest.json"
        manifest.record_counts("fetched", 500)
        manifest.save(path)
        data = json.loads(path.read_text())
        assert data["run_id"] == manifest.run_id
        assert data["run_date"] == "2025-06-01"
        assert data["build_name"] == "yfv-brazil"
        assert data["counts"]["fetched"] == 500

    def test_save_creates_parent_directory(self, manifest, tmp_path):
        path = tmp_path / "subdir" / "manifest.json"
        manifest.save(path)
        assert path.exists()

    def test_tool_versions_in_output(self, manifest, tmp_path):
        path = tmp_path / "manifest.json"
        manifest.save(path)
        data = json.loads(path.read_text())
        assert "tool_versions" in data
        assert "flexpipe" in data["tool_versions"]

    def test_extra_fields_included(self, manifest, tmp_path):
        manifest.record("data_source", "pathoplexus")
        path = tmp_path / "manifest.json"
        manifest.save(path)
        data = json.loads(path.read_text())
        assert data["data_source"] == "pathoplexus"


class TestManifestBoundaryCheck:
    """validate_boundary() — ingest→phylo column contract."""

    def _write_metadata(self, tmp_path, columns):
        df = pd.DataFrame({col: ["x"] for col in columns})
        path = tmp_path / "metadata.tsv"
        df.to_csv(path, sep="\t", index=False)
        return path

    def test_passes_with_all_required_columns(self, manifest, tmp_path):
        path = self._write_metadata(tmp_path, BOUNDARY_REQUIRED_COLUMNS)
        manifest.validate_boundary(path)  # must not raise

    def test_passes_with_extra_columns(self, manifest, tmp_path):
        cols = BOUNDARY_REQUIRED_COLUMNS | {"host", "genome_quality", "extra_col"}
        path = self._write_metadata(tmp_path, cols)
        manifest.validate_boundary(path)  # must not raise

    def test_fails_missing_columns(self, manifest, tmp_path):
        cols = BOUNDARY_REQUIRED_COLUMNS - {"clade_truncated", "region"}
        path = self._write_metadata(tmp_path, cols)
        with pytest.raises(SystemExit) as exc_info:
            manifest.validate_boundary(path)
        msg = str(exc_info.value)
        assert "clade_truncated" in msg or "region" in msg

    def test_fails_missing_file(self, manifest, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            manifest.validate_boundary(tmp_path / "nonexistent.tsv")
        assert "not found" in str(exc_info.value).lower()

    def test_required_columns_set_not_empty(self):
        """The required columns set must contain at least the core pipeline columns."""
        assert "strain" in BOUNDARY_REQUIRED_COLUMNS
        assert "date" in BOUNDARY_REQUIRED_COLUMNS
        assert "clade" in BOUNDARY_REQUIRED_COLUMNS
        assert "clade_truncated" in BOUNDARY_REQUIRED_COLUMNS
