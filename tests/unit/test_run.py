"""Unit tests for flexpipe.run — orchestrator exit-code contract."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import filelock
import pytest
import yaml

from flexpipe.config import FlexpipeConfig, ViralqcConfig
from flexpipe.paths import WorkdirPaths
from flexpipe.run import _materialize_backbone, _run_snakemake, run_pipeline, validate_run_date

FIXTURE_CONFIG = Path(__file__).parent.parent / "fixtures" / "config_division_build.yaml"


def _make_mock_cfg():
    """Return a minimal valid FlexpipeConfig for orchestrator tests."""
    return FlexpipeConfig(
        data_source="pathoplexus",
        pathoplexus={"organism": "yellow-fever"},
        viralqc=ViralqcConfig(
            datasets_dir="/tmp/viralQC/datasets",
            blast_database="/tmp/viralQC/datasets/blast.fasta",
            blast_database_metadata="/tmp/viralQC/datasets/blast.tsv",
        ),
    )


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
    # Write header + 10 data rows so the default min_sequences=10 guardrail is satisfied.
    lines = ["\t".join(required_cols)]
    for i in range(10):
        lines.append(
            "\t".join(
                [
                    f"seq{i}",
                    "2026-01-01",
                    "Brazil",
                    "SP",
                    "SP",
                    "I",
                    "I",
                    "South America",
                    "human",
                    "Pathoplexus",
                    "OPEN",
                ]
            )
        )
    (sub_dir / "metadata.tsv").write_text("\n".join(lines) + "\n")
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

    def test_bad_run_date_returns_2(self, patch_run, tmp_path):
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-99-99",
            stage="ingest",
        )
        assert rc == 2

    def test_validate_run_date_rejects_non_iso(self):
        with pytest.raises(SystemExit, match="YYYY-MM-DD"):
            validate_run_date("20260606")


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

    def test_manifest_contains_expanded_provenance(self, patch_run, tmp_path):
        run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-06-05",
            stage="ingest",
        )
        data = json.loads((tmp_path / "manifest.json").read_text())
        assert "resolved_config_digest" in data
        assert "resolved_inputs" in data
        assert "git" in data
        assert "viralqc" in data


class TestRunSnakemakeCommand:
    def test_uses_resolved_config_as_sole_configfile(self, monkeypatch, tmp_path):
        """Resolved config is the only --configfile (Snakemake 9+ loads only the last one)."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return MagicMock(returncode=0)

        monkeypatch.setattr("flexpipe.run.subprocess.run", fake_run)

        overrides = tmp_path / "snakemake_resolved.yaml"
        overrides.write_text("viralqc:\n  datasets_dir: /foo\n")
        build_config = Path("builds/yfv-brazil/config.yaml")

        _run_snakemake(
            snakefile=Path("ingest/Snakefile"),
            config_path=build_config,
            paths=WorkdirPaths.from_root(tmp_path / "workdir"),
            cores=2,
            config_overrides=overrides,
        )

        cmd = captured["cmd"]
        configfile_args = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--configfile"]
        # Exactly one --configfile: the resolved config (not the raw build config)
        assert len(configfile_args) == 1, f"Expected 1 --configfile, got: {configfile_args}"
        assert str(overrides) in configfile_args

        # build_config must be passed as an explicit --config key so flexpipe-* CLIs
        # receive the full build config path without relying on path heuristics.
        config_tokens = [t for t in cmd if t.startswith("build_config=")]
        assert len(config_tokens) == 1, "build_config= not found in --config args"
        assert config_tokens[0] == f"build_config={build_config}"

    def test_run_date_forwarded_to_snakemake(self, monkeypatch, tmp_path):
        """run_date is passed as --config run_date=<date> to both ingest and phylo stages."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.setdefault("cmds", []).append(cmd)
            return MagicMock(returncode=0)

        monkeypatch.setattr("flexpipe.run.subprocess.run", fake_run)

        overrides = tmp_path / "snakemake_resolved.yaml"
        overrides.write_text("viralqc:\n  datasets_dir: /foo\n")
        build_config = Path("builds/yfv-brazil/config.yaml")

        _run_snakemake(
            snakefile=Path("ingest/Snakefile"),
            config_path=build_config,
            paths=WorkdirPaths.from_root(tmp_path / "workdir"),
            cores=2,
            config_overrides=overrides,
            run_date="2026-01-01",
        )

        cmd = captured["cmds"][0]
        run_date_tokens = [t for t in cmd if t.startswith("run_date=")]
        assert run_date_tokens == ["run_date=2026-01-01"]

    def test_run_date_absent_when_empty(self, monkeypatch, tmp_path):
        """No run_date= token when run_date is empty (direct snakemake invocation path)."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return MagicMock(returncode=0)

        monkeypatch.setattr("flexpipe.run.subprocess.run", fake_run)

        overrides = tmp_path / "snakemake_resolved.yaml"
        overrides.write_text("viralqc:\n  datasets_dir: /foo\n")
        build_config = Path("builds/yfv-brazil/config.yaml")

        _run_snakemake(
            snakefile=Path("ingest/Snakefile"),
            config_path=build_config,
            paths=WorkdirPaths.from_root(tmp_path / "workdir"),
            cores=2,
            config_overrides=overrides,
            run_date="",
        )

        cmd = captured["cmd"]
        run_date_tokens = [t for t in cmd if t.startswith("run_date=")]
        assert run_date_tokens == [], "run_date= token must be absent when run_date is empty"

    def test_run_pipeline_forwards_run_date_to_snakemake(self, patch_run, tmp_path):
        """run_pipeline passes run_date through to _run_snakemake."""
        run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-03-15",
            stage="ingest",
        )
        call_args = patch_run.call_args_list
        assert len(call_args) == 1
        # _run_snakemake receives run_date as a keyword arg
        _, kwargs = call_args[0]
        assert kwargs.get("run_date") == "2026-03-15"

    def test_writes_resolved_config_during_run(self, patch_run, tmp_path):
        run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-06-05",
            stage="ingest",
        )
        resolved = tmp_path / "config" / "snakemake_resolved.yaml"
        assert resolved.exists()
        data = yaml.safe_load(resolved.read_text())
        # Resolved viralqc paths are written
        assert data["viralqc"]["datasets_dir"] == "/tmp/viralQC/datasets"
        # Full build config keys are preserved (not just viralqc)
        fixture_keys = yaml.safe_load(FIXTURE_CONFIG.read_text()).keys()
        for key in fixture_keys:
            assert key in data, f"Key '{key}' from build config missing in resolved config"


class TestWorkdirLock:
    """Workdir filelock prevents concurrent runs on the same directory."""

    def test_second_run_returns_2_when_locked(self, patch_run, tmp_path):
        """A second run_pipeline call with the same workdir fails fast with exit code 2."""
        # Manually acquire the lock to simulate a concurrent process holding it.
        lock_path = tmp_path / ".flexpipe.lock"
        lock = filelock.FileLock(str(lock_path), timeout=0)
        lock.acquire()
        try:
            rc = run_pipeline(
                config_path=FIXTURE_CONFIG,
                workdir=tmp_path,
                run_date="2026-01-01",
            )
            assert rc == 2, f"Expected exit code 2 (workdir locked), got {rc}"
        finally:
            lock.release()

    def test_lock_released_after_successful_run(self, patch_run, tmp_path):
        """After a successful run the lock file is released (a second run can proceed)."""
        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
        )
        assert rc == 0
        # Lock must be releaseable by a fresh FileLock — i.e. not still held.
        lock = filelock.FileLock(str(tmp_path / ".flexpipe.lock"), timeout=0)
        lock.acquire()
        lock.release()  # would raise filelock.Timeout if still held


class TestMinSequencesGuardrail:
    """min_sequences in QcConfig gates the phylo stage."""

    def _make_cfg_with_min_sequences(self, n: int) -> FlexpipeConfig:
        return FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            viralqc=ViralqcConfig(
                datasets_dir="/tmp/viralQC/datasets",
                blast_database="/tmp/viralQC/datasets/blast.fasta",
                blast_database_metadata="/tmp/viralQC/datasets/blast.tsv",
            ),
            qc={
                "min_sequences": n,
                "genome_quality": ["A", "B"],
                "min_coverage": 0.70,
                "required_columns": ["strain", "date", "clade"],
            },
        )

    def _write_metadata(self, path: Path, n_rows: int) -> None:
        cols = [
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
        lines = ["\t".join(cols)]
        for i in range(n_rows):
            lines.append(
                "\t".join(
                    [
                        f"s{i}",
                        "2026-01-01",
                        "Brazil",
                        "SP",
                        "SP",
                        "I",
                        "I",
                        "South America",
                        "human",
                        "Pathoplexus",
                        "OPEN",
                    ]
                )
            )
        path.write_text("\n".join(lines) + "\n")

    def test_guardrail_blocks_when_too_few_sequences(self, monkeypatch, tmp_path):
        """run_pipeline returns 1 when subsampled rows < min_sequences."""
        monkeypatch.setattr(
            "flexpipe.run.load_config",
            lambda *a, **kw: self._make_cfg_with_min_sequences(10),
        )
        monkeypatch.setattr("flexpipe.run._run_snakemake", MagicMock(return_value=0))

        sub_dir = tmp_path / "results" / "subsampled"
        sub_dir.mkdir(parents=True)
        # Write only 5 rows — below min_sequences=10
        self._write_metadata(sub_dir / "metadata.tsv", 5)

        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="phylo",
        )
        assert rc == 1

    def test_guardrail_passes_when_enough_sequences(self, monkeypatch, tmp_path):
        """run_pipeline succeeds when subsampled rows >= min_sequences."""
        monkeypatch.setattr(
            "flexpipe.run.load_config",
            lambda *a, **kw: self._make_cfg_with_min_sequences(5),
        )
        monkeypatch.setattr("flexpipe.run._run_snakemake", MagicMock(return_value=0))

        sub_dir = tmp_path / "results" / "subsampled"
        sub_dir.mkdir(parents=True)
        # Write 10 rows — above min_sequences=5
        self._write_metadata(sub_dir / "metadata.tsv", 10)

        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="phylo",
        )
        assert rc == 0

    def test_guardrail_disabled_with_min_sequences_zero(self, monkeypatch, tmp_path):
        """min_sequences=0 disables the guardrail (backward-compatible)."""
        monkeypatch.setattr(
            "flexpipe.run.load_config",
            lambda *a, **kw: self._make_cfg_with_min_sequences(0),
        )
        monkeypatch.setattr("flexpipe.run._run_snakemake", MagicMock(return_value=0))

        sub_dir = tmp_path / "results" / "subsampled"
        sub_dir.mkdir(parents=True)
        # Write 0 data rows — guardrail must be skipped
        self._write_metadata(sub_dir / "metadata.tsv", 0)

        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=tmp_path,
            run_date="2026-01-01",
            stage="phylo",
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# _materialize_backbone
# ---------------------------------------------------------------------------


def _write_prev_metadata(prev_workdir: Path, strains: list[str]) -> None:
    """Write a minimal subsampled metadata TSV to simulate a previous run."""
    meta_dir = prev_workdir / "results" / "subsampled"
    meta_dir.mkdir(parents=True)
    cols = ["strain", "date", "country"]
    lines = ["\t".join(cols)]
    for s in strains:
        lines.append(f"{s}\t2024-01-01\tBrazil")
    (meta_dir / "metadata.tsv").write_text("\n".join(lines) + "\n")


class TestMaterializeBackbone:
    """_materialize_backbone edge-case and happy-path coverage."""

    def test_none_backbone_from_returns_none(self, tmp_path):
        paths = WorkdirPaths.from_root(tmp_path / "current")
        paths.ensure_dirs()
        assert _materialize_backbone(None, paths) is None

    def test_happy_path_writes_strain_file(self, tmp_path):
        prev = tmp_path / "prev"
        current = tmp_path / "current"
        _write_prev_metadata(prev, ["strainA", "strainB", "strainC"])
        paths = WorkdirPaths.from_root(current)
        paths.ensure_dirs()

        result = _materialize_backbone(prev, paths)

        assert result is not None
        assert result == paths.backbone_strains
        content = result.read_text().splitlines()
        assert set(content) == {"strainA", "strainB", "strainC"}

    def test_happy_path_strain_count(self, tmp_path):
        prev = tmp_path / "prev"
        current = tmp_path / "current"
        _write_prev_metadata(prev, [f"s{i}" for i in range(10)])
        paths = WorkdirPaths.from_root(current)
        paths.ensure_dirs()

        result = _materialize_backbone(prev, paths)
        assert result is not None
        assert len(result.read_text().splitlines()) == 10

    def test_missing_previous_metadata_returns_none(self, tmp_path):
        prev = tmp_path / "prev_that_doesnt_exist"
        current = tmp_path / "current"
        paths = WorkdirPaths.from_root(current)
        paths.ensure_dirs()
        # No metadata file at prev — must gracefully return None
        assert _materialize_backbone(prev, paths) is None

    def test_empty_previous_metadata_returns_none(self, tmp_path):
        prev = tmp_path / "prev"
        current = tmp_path / "current"
        _write_prev_metadata(prev, [])  # header only, no strains
        paths = WorkdirPaths.from_root(current)
        paths.ensure_dirs()
        assert _materialize_backbone(prev, paths) is None

    def test_self_reference_raises_system_exit(self, tmp_path):
        paths = WorkdirPaths.from_root(tmp_path)
        paths.ensure_dirs()
        with pytest.raises(SystemExit, match="current workdir"):
            _materialize_backbone(tmp_path, paths)

    def test_backbone_from_propagates_to_run_pipeline(self, monkeypatch, tmp_path):
        """run_pipeline passes backbone_from through and cfg gets backbone_strains set."""
        prev = tmp_path / "prev"
        current = tmp_path / "current"
        _write_prev_metadata(prev, ["strain1", "strain2"])

        # Also satisfy the subsampled-metadata boundary check
        sub_dir = current / "results" / "subsampled"
        sub_dir.mkdir(parents=True)
        cols = [
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
        lines = ["\t".join(cols)]
        for i in range(10):
            lines.append(
                "\t".join(
                    [
                        f"seq{i}",
                        "2026-01-01",
                        "Brazil",
                        "SP",
                        "SP",
                        "I",
                        "I",
                        "South America",
                        "human",
                        "Pathoplexus",
                        "OPEN",
                    ]
                )
            )
        (sub_dir / "metadata.tsv").write_text("\n".join(lines) + "\n")

        monkeypatch.setattr("flexpipe.run.load_config", lambda *a, **kw: _make_mock_cfg())
        mock_snakemake = MagicMock(return_value=0)
        monkeypatch.setattr("flexpipe.run._run_snakemake", mock_snakemake)

        rc = run_pipeline(
            config_path=FIXTURE_CONFIG,
            workdir=current,
            run_date="2026-06-01",
            stage="ingest",
            backbone_from=prev,
        )
        assert rc == 0
        # backbone_strains.txt must have been written in the current workdir
        assert (current / "config" / "backbone_strains.txt").exists()
        content = (current / "config" / "backbone_strains.txt").read_text().splitlines()
        assert set(content) == {"strain1", "strain2"}
