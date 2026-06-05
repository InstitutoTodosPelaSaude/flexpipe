"""Unit tests for flexpipe.run — orchestrator exit-code contract."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from flexpipe.run import run_pipeline

FIXTURE_CONFIG = Path(__file__).parent.parent / "fixtures" / "config_division_build.yaml"


def _make_mock_cfg():
    """Return a minimal valid FlexpipeConfig-like mock."""
    return MagicMock()


@pytest.fixture()
def patch_run(monkeypatch, tmp_path):
    """Patch load_config and _run_snakemake to isolate from external tools.

    Also creates the subsampled metadata file that the boundary check requires
    when running stage='all'.
    """
    monkeypatch.setattr("flexpipe.run.load_config", lambda *a, **kw: _make_mock_cfg())
    # Satisfy the boundary check by creating a minimal subsampled metadata TSV
    sub_dir = tmp_path / "results" / "subsampled"
    sub_dir.mkdir(parents=True)
    required_cols = [
        "strain",
        "date",
        "country",
        "division",
        "location",
        "clade",
        "clade_truncated",
        "region",
        "host",
        "source",
        "data_use",
    ]
    (sub_dir / "metadata.tsv").write_text("\t".join(required_cols) + "\n")
    mock = MagicMock(return_value=0)
    monkeypatch.setattr("flexpipe.run._run_snakemake", mock)
    return mock


@pytest.fixture()
def patch_run_fail(monkeypatch):
    """Patch _run_snakemake to always return exit code 1 (failure)."""
    monkeypatch.setattr("flexpipe.run.load_config", lambda *a, **kw: _make_mock_cfg())
    mock = MagicMock(return_value=1)
    monkeypatch.setattr("flexpipe.run._run_snakemake", mock)
    return mock


class TestRunPipelineExitCodes:
    def test_all_stages_success_returns_0(self, patch_run, tmp_path):
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="all",
        )
        assert rc == 0

    def test_ingest_only_success_returns_0(self, patch_run, tmp_path):
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="ingest",
        )
        assert rc == 0

    def test_ingest_failure_returns_nonzero(self, patch_run_fail, tmp_path):
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="ingest",
        )
        assert rc != 0

    def test_ingest_failure_in_all_stage_stops_early(self, patch_run_fail, tmp_path):
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="all",
        )
        assert rc != 0
        # Only ingest _run_snakemake call — phylo must not run after ingest failure
        assert patch_run_fail.call_count == 1

    def test_phylo_only_runs_one_snakemake(self, patch_run, tmp_path):
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="phylo",
        )
        assert rc == 0
        assert patch_run.call_count == 1

    def test_all_runs_two_snakemake_calls(self, patch_run, tmp_path):
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="all",
        )
        assert rc == 0
        assert patch_run.call_count == 2

    def test_bad_config_returns_2(self, monkeypatch, tmp_path):
        """load_config raising SystemExit → run_pipeline returns 2."""

        def _bad_load(*a, **kw):
            raise SystemExit("Config error: invalid data_source")

        monkeypatch.setattr("flexpipe.run.load_config", _bad_load)
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
        )
        assert rc == 2


class TestRunPipelineManifest:
    def test_manifest_written(self, patch_run, tmp_path):
        run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-06-05",
            stage="ingest",
        )
        assert (tmp_path / "manifest.json").exists()

    def test_manifest_contains_stage(self, patch_run, tmp_path):
        run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-06-05",
            stage="ingest",
        )
        data = json.loads((tmp_path / "manifest.json").read_text())
        assert data.get("stage") == "ingest"

    def test_manifest_run_date_recorded(self, patch_run, tmp_path):
        run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-06-05",
            stage="ingest",
        )
        data = json.loads((tmp_path / "manifest.json").read_text())
        assert data.get("run_date") == "2026-06-05"
