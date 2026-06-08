"""Integration tests: Snakemake dry-run wiring for the ingest stage.

These tests invoke ``snakemake --dry-run --printshellcmds`` (no real data) to verify
two key wiring invariants that are hard to catch with unit tests alone:

1. ``flexpipe-curate`` and other flexpipe-* CLIs receive ``--config <build>/config.yaml``
   (the full build config path), **never** the workdir-local resolved config.

2. The ``viralqc`` rule receives a non-empty ``--datasets-dir`` path, confirming that the
   resolved ViralQC paths written by ``write_snakemake_config_overrides`` are picked up by
   Snakemake params.

The resolved config is the **sole** ``--configfile``: it is the full build config merged
with pydantic-resolved ViralQC paths (Snakemake 9+ only loads the last --configfile, so
a single complete file is required).

These tests use no real data, network access, or conda envs — just the Snakemake DAG
planner (dry-run mode).  They are tagged ``integration`` because they shell out to
``snakemake`` and therefore require the nextstrain environment to be active.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from flexpipe.config import FlexpipeConfig, ViralqcConfig, write_snakemake_config_overrides
from tests.integration.conftest import all_build_configs

# Repository root is three levels up from this file: tests/integration/ → tests/ → repo
REPO_ROOT = Path(__file__).parent.parent.parent
INGEST_SNAKEFILE = REPO_ROOT / "ingest" / "Snakefile"
BUILD_CONFIG = REPO_ROOT / "builds" / "yfv-brazil" / "config.yaml"
RSV_BUILD_CONFIG = REPO_ROOT / "builds" / "rsv-global" / "config.yaml"
LOCAL_BUILD_CONFIG = REPO_ROOT / "builds" / "local-example" / "config.yaml"
# Archetype-specific lists for targeted assertion tests (kept for correctness checks).
DENV_BUILD_CONFIGS = [
    REPO_ROOT / "builds" / "denv1-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "denv2-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "denv3-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "denv4-brazil" / "config.yaml",
]
NCBI_BRAZIL_BUILD_CONFIGS = [
    REPO_ROOT / "builds" / "zikv-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "chikv-brazil" / "config.yaml",
]
PPX_BRAZIL_BUILD_CONFIGS = [
    REPO_ROOT / "builds" / "rsv-a-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "rsv-b-brazil" / "config.yaml",
]
SEGMENT_BRAZIL_BUILD_CONFIGS = [
    REPO_ROOT / "builds" / "orov-l-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "flu-h1n1-ha-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "flu-h3n2-ha-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "flu-b-ha-brazil" / "config.yaml",
]
# AUTO-DISCOVERED: all builds/*/config.yaml. New builds are covered automatically.
BUILD_CONFIGS = all_build_configs()

# Sentinel paths used in the fake ViralQC config; chosen to be distinctive and
# absolute so they appear verbatim in the rendered shell commands.
FAKE_DATASETS_DIR = "/fake/viralqc/datasets"
FAKE_BLAST_DB = "/fake/viralqc/datasets/blast.fasta"
FAKE_BLAST_META = "/fake/viralqc/datasets/blast.tsv"


@pytest.fixture()
def resolved_config(tmp_path):
    """Write a complete resolved config using the real write_snakemake_config_overrides.

    This is the sole --configfile the ingest Snakefile receives: full build config
    content merged with fake-but-non-empty ViralQC paths for wiring validation.
    """
    cfg = FlexpipeConfig(
        data_source="pathoplexus",
        pathoplexus={"organism": "yellow-fever"},
        viralqc=ViralqcConfig(
            datasets_dir=FAKE_DATASETS_DIR,
            blast_database=FAKE_BLAST_DB,
            blast_database_metadata=FAKE_BLAST_META,
        ),
    )
    p = tmp_path / "snakemake_resolved.yaml"
    return write_snakemake_config_overrides(cfg, p, BUILD_CONFIG)


@pytest.fixture()
def direct_viralqc_resolved_config(tmp_path):
    cfg = FlexpipeConfig(
        data_source="pathoplexus",
        pathoplexus={"organism": "yellow-fever"},
        viralqc=ViralqcConfig(
            datasets_dir=FAKE_DATASETS_DIR,
            blast_database=FAKE_BLAST_DB,
            blast_database_metadata=FAKE_BLAST_META,
            runner="direct",
            executable="/opt/viral qc/vqc",
        ),
    )
    p = tmp_path / "snakemake_resolved_direct.yaml"
    return write_snakemake_config_overrides(cfg, p, BUILD_CONFIG)


def _dry_run(tmp_path, resolved_config, build_config=None, cwd=None):
    """Run ``snakemake -n -p`` on the ingest Snakefile and return captured output.

    Args:
        build_config: Path to the build config.yaml passed as ``build_config``
            Snakemake config key.  Defaults to the YFV-Brazil config.
        cwd: Process working directory for Snakemake.  Defaults to the repo root.

    Returns:
        (combined_output, return_code)

    Raises:
        pytest.skip if snakemake is not found on PATH.
    """
    if not shutil.which("snakemake"):
        pytest.skip("snakemake not found on PATH — activate the nextstrain conda env")

    if build_config is None:
        build_config = BUILD_CONFIG
    if cwd is None:
        cwd = REPO_ROOT

    workdir = tmp_path / "workdir"
    cmd = [
        "snakemake",
        "--snakefile",
        str(INGEST_SNAKEFILE),
        "--configfile",
        str(resolved_config),
        "--config",
        f"workdir={workdir}",
        f"build_config={build_config}",
        "--dry-run",
        "--printshellcmds",
        "--cores",
        "1",
        "--nolock",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    combined = result.stdout + "\n" + result.stderr
    return combined, result.returncode


def _dry_run_with_run_date(tmp_path, resolved_config, run_date):
    """Like _dry_run but also passes --config run_date=<run_date>."""
    if not shutil.which("snakemake"):
        pytest.skip("snakemake not found on PATH — activate the nextstrain conda env")

    workdir = tmp_path / "workdir"
    cmd = [
        "snakemake",
        "--snakefile",
        str(INGEST_SNAKEFILE),
        "--configfile",
        str(resolved_config),
        "--config",
        f"workdir={workdir}",
        f"build_config={BUILD_CONFIG}",
        f"run_date={run_date}",
        "--dry-run",
        "--printshellcmds",
        "--cores",
        "1",
        "--nolock",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    combined = result.stdout + "\n" + result.stderr
    return combined, result.returncode


def _resolved_config_for_build(tmp_path, build_config: Path):
    """Write a fake-ViralQC resolved config for any scaffold build."""
    raw = yaml.safe_load(build_config.read_text())
    data_source = raw.get("data_source", "pathoplexus")
    cfg_kwargs = {
        "data_source": data_source,
        "viralqc": ViralqcConfig(
            datasets_dir=FAKE_DATASETS_DIR,
            blast_database=FAKE_BLAST_DB,
            blast_database_metadata=FAKE_BLAST_META,
        ),
    }
    if data_source == "pathoplexus":
        cfg_kwargs["pathoplexus"] = raw.get("pathoplexus", {})
    elif data_source == "ncbi":
        ncbi = dict(raw.get("ncbi", {}))
        ncbi.setdefault("email", "ops@example.org")
        if not ncbi.get("email"):
            ncbi["email"] = "ops@example.org"
        cfg_kwargs["ncbi"] = ncbi
    elif data_source == "local":
        # local.metadata / local.sequences are raw (relative) paths here;
        # write_snakemake_config_overrides → resolve_config_paths turns them absolute.
        cfg_kwargs["local"] = raw.get("local", {})

    cfg = FlexpipeConfig(**cfg_kwargs)
    p = tmp_path / f"snakemake_resolved_{build_config.parent.name}.yaml"
    return write_snakemake_config_overrides(cfg, p, build_config)


@pytest.mark.integration
class TestIngestWiring:
    @pytest.mark.parametrize("build_config", BUILD_CONFIGS, ids=lambda p: p.parent.name)
    def test_all_scaffold_builds_dry_run(self, tmp_path, build_config):
        """Every build scaffold can plan the ingest DAG without real data or ViralQC paths."""
        resolved_config = _resolved_config_for_build(tmp_path, build_config)
        output, rc = _dry_run(tmp_path, resolved_config, build_config=build_config)
        assert rc == 0, (
            f"{build_config.parent.name} snakemake dry-run exited with code {rc}.\n"
            f"Output:\n{output}"
        )

    @pytest.mark.parametrize("build_config", DENV_BUILD_CONFIGS, ids=lambda p: p.parent.name)
    def test_denv_builds_schedule_pathoplexus_not_ncbi(self, tmp_path, build_config):
        """DENV builds use the shared Pathoplexus dengue endpoint plus config query params."""
        resolved_config = _resolved_config_for_build(tmp_path, build_config)
        output, rc = _dry_run(tmp_path, resolved_config, build_config=build_config)
        assert rc == 0, f"dry-run failed:\n{output}"
        assert "fetch_pathoplexus" in output
        assert "fetch_ncbi" not in output
        assert str(build_config) in output

    @pytest.mark.parametrize("build_config", DENV_BUILD_CONFIGS, ids=lambda p: p.parent.name)
    def test_denv_reference_builds_render_new_visual_hierarchies(self, tmp_path, build_config):
        """All DENV ingest dry-runs carry the new geo and lineage color levels."""
        resolved_config = _resolved_config_for_build(tmp_path, build_config)
        output, rc = _dry_run(tmp_path, resolved_config, build_config=build_config)
        assert rc == 0, f"dry-run failed:\n{output}"
        assert "--columns  country division location" in output
        assert "--levels  continent country division location" in output
        assert "--levels  serotype genotype major_lineage minor_lineage clade" in output

    def test_dry_run_succeeds(self, tmp_path, resolved_config):
        """Snakemake can plan the full ingest DAG without errors."""
        output, rc = _dry_run(tmp_path, resolved_config)
        assert rc == 0, f"snakemake dry-run exited with code {rc}.\n" f"Output:\n{output}"
        assert "flexpipe-normalize-dates" in output
        assert "date_normalization.tsv" in output

    def test_flexpipe_curate_uses_build_config_not_resolved_config(self, tmp_path, resolved_config):
        """flexpipe-curate must receive the build config path, not the workdir resolved config."""
        output, rc = _dry_run(tmp_path, resolved_config)
        assert rc == 0, f"dry-run failed:\n{output}"

        curate_lines = [ln for ln in output.splitlines() if "flexpipe-curate" in ln]
        assert curate_lines, "flexpipe-curate command not found in dry-run output"

        for line in curate_lines:
            assert str(BUILD_CONFIG) in line, (
                f"flexpipe-curate was not given the build config path.\n"
                f"Line: {line!r}\n"
                f"Expected: {BUILD_CONFIG}"
            )
            assert "snakemake_resolved.yaml" not in line, (
                f"flexpipe-curate received the resolved config instead of the build config.\n"
                f"Line: {line!r}"
            )

    def test_viralqc_rule_has_non_empty_datasets_dir(self, tmp_path, resolved_config):
        """The viralqc rule must use the resolved --datasets-dir, not an empty string."""
        output, rc = _dry_run(tmp_path, resolved_config)
        assert rc == 0, f"dry-run failed:\n{output}"

        vqc_lines = [ln for ln in output.splitlines() if "--datasets-dir" in ln]
        assert vqc_lines, "vqc --datasets-dir argument not found in dry-run output"

        for line in vqc_lines:
            idx = line.find("--datasets-dir")
            remainder = line[idx + len("--datasets-dir") :].strip()
            assert remainder and not remainder.startswith(
                "--"
            ), f"--datasets-dir is empty or missing its argument.\nLine: {line!r}"
            assert FAKE_DATASETS_DIR in line, (
                f"Expected fake datasets dir {FAKE_DATASETS_DIR!r} in viralqc command.\n"
                f"Line: {line!r}"
            )

    def test_viralqc_threads_are_capped_by_snakemake_cores(self, tmp_path, resolved_config):
        """The viralqc command must use Snakemake's capped rule threads."""
        output, rc = _dry_run(tmp_path, resolved_config)
        assert rc == 0, f"dry-run failed:\n{output}"
        vqc_lines = [ln for ln in output.splitlines() if "--cores" in ln]
        assert vqc_lines, "viralqc --cores argument not found in dry-run output"
        assert any("--cores                   1" in line for line in vqc_lines), output
        assert "no sequences available for ViralQC" in output

    def test_viralqc_direct_runner_is_rendered(self, tmp_path, direct_viralqc_resolved_config):
        output, rc = _dry_run(tmp_path, direct_viralqc_resolved_config)
        assert rc == 0, f"dry-run failed:\n{output}"
        assert "'/opt/viral qc/vqc' run" in output

    def test_dry_run_with_run_date_schedules_resolve_subsample_config(
        self, tmp_path, resolved_config
    ):
        """Passing run_date causes the resolve_subsample_config rule to be scheduled."""
        output, rc = _dry_run_with_run_date(tmp_path, resolved_config, "2026-01-01")
        assert rc == 0, f"dry-run with run_date failed:\n{output}"
        assert "resolve_subsample_config" in output, (
            "resolve_subsample_config rule was not scheduled.\n" f"Output:\n{output}"
        )
        assert "--run-date 2026-01-01" in output

    def test_dry_run_with_run_date_subsample_uses_resolved_config(self, tmp_path, resolved_config):
        """The prepare rule (augur subsample) must consume subsample_resolved.yaml."""
        output, rc = _dry_run_with_run_date(tmp_path, resolved_config, "2026-01-01")
        assert rc == 0, f"dry-run with run_date failed:\n{output}"

        subsample_lines = [ln for ln in output.splitlines() if "augur subsample" in ln]
        assert subsample_lines, "augur subsample command not found in dry-run output"

        for line in subsample_lines:
            assert "subsample_resolved.yaml" in line, (
                f"augur subsample was not given the workdir-resolved subsample config.\n"
                f"Line: {line!r}"
            )

    def test_dry_run_succeeds_from_outside_repo(self, tmp_path, resolved_config):
        """Resolved build paths must make ingest independent of the caller's cwd."""
        outside = tmp_path / "outside"
        outside.mkdir()
        output, rc = _dry_run(tmp_path, resolved_config, cwd=outside)
        assert rc == 0, f"snakemake dry-run from outside repo failed:\n{output}"
        assert str(BUILD_CONFIG) in output


# ---------------------------------------------------------------------------
# RSV-A global build — NCBI source + region_source: country
# ---------------------------------------------------------------------------


@pytest.fixture()
def rsv_resolved_config(tmp_path):
    """Write a complete resolved config for the RSV-A global build.

    Uses NCBI as data source (taxid 208893) with fake-but-non-empty ViralQC
    paths so the DAG can be planned without a real viralQC installation.
    """
    cfg = FlexpipeConfig(
        data_source="ncbi",
        ncbi={"taxid": 208893, "genome_size": 15200, "email": "ops@example.org"},
        viralqc=ViralqcConfig(
            datasets_dir=FAKE_DATASETS_DIR,
            blast_database=FAKE_BLAST_DB,
            blast_database_metadata=FAKE_BLAST_META,
        ),
    )
    p = tmp_path / "snakemake_resolved_rsv.yaml"
    return write_snakemake_config_overrides(cfg, p, RSV_BUILD_CONFIG)


@pytest.mark.integration
class TestRsvIngestWiring:
    """Verify the NCBI + country-region ingest DAG using the rsv-global build scaffold.

    These tests prove that the ``data_source: ncbi`` / ``region_source: country``
    generalisation path is correctly wired without requiring a real NCBI fetch,
    ViralQC dataset, or RSV reference genome.
    """

    def test_dry_run_succeeds(self, tmp_path, rsv_resolved_config):
        """Snakemake can plan the full RSV ingest DAG without errors."""
        output, rc = _dry_run(tmp_path, rsv_resolved_config, build_config=RSV_BUILD_CONFIG)
        assert rc == 0, f"snakemake dry-run exited with code {rc}.\nOutput:\n{output}"

    def test_fetch_ncbi_is_scheduled_not_pathoplexus(self, tmp_path, rsv_resolved_config):
        """fetch_ncbi must be planned; fetch_pathoplexus must not appear in the DAG."""
        output, rc = _dry_run(tmp_path, rsv_resolved_config, build_config=RSV_BUILD_CONFIG)
        assert rc == 0, f"dry-run failed:\n{output}"

        assert "fetch_ncbi" in output, (
            "fetch_ncbi rule was not found in the dry-run output.\n" f"Output:\n{output}"
        )
        assert "fetch_pathoplexus" not in output, (
            "fetch_pathoplexus appeared in the RSV dry-run — should be fetch_ncbi only.\n"
            f"Output:\n{output}"
        )

    def test_flexpipe_curate_uses_rsv_build_config(self, tmp_path, rsv_resolved_config):
        """flexpipe-curate must receive the RSV build config path, not the resolved config."""
        output, rc = _dry_run(tmp_path, rsv_resolved_config, build_config=RSV_BUILD_CONFIG)
        assert rc == 0, f"dry-run failed:\n{output}"

        curate_lines = [ln for ln in output.splitlines() if "flexpipe-curate" in ln]
        assert curate_lines, "flexpipe-curate command not found in dry-run output"

        for line in curate_lines:
            assert str(RSV_BUILD_CONFIG) in line, (
                f"flexpipe-curate was not given the RSV build config path.\n"
                f"Line: {line!r}\n"
                f"Expected: {RSV_BUILD_CONFIG}"
            )
            assert "snakemake_resolved" not in line, (
                f"flexpipe-curate received the resolved config instead of the build config.\n"
                f"Line: {line!r}"
            )

    def test_dry_run_succeeds_from_outside_repo(self, tmp_path, rsv_resolved_config):
        """The RSV scaffold also plans correctly when invoked from another cwd."""
        outside = tmp_path / "outside"
        outside.mkdir()
        output, rc = _dry_run(
            tmp_path,
            rsv_resolved_config,
            build_config=RSV_BUILD_CONFIG,
            cwd=outside,
        )
        assert rc == 0, f"RSV dry-run from outside repo failed:\n{output}"
        assert str(RSV_BUILD_CONFIG) in output


# ---------------------------------------------------------------------------
# Local data-source build — data_source: local (no remote fetch)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLocalIngestWiring:
    """Verify the ``data_source: local`` ingest DAG using the local-example build scaffold.

    These tests confirm that when a user provides pre-collected metadata and sequences,
    the DAG plans a ``fetch_local`` copy step (no network), a passthrough merge, and
    the full QC → subsample → colours/coordinates chain — without ever scheduling
    ``fetch_pathoplexus`` or ``fetch_ncbi``.
    """

    def test_dry_run_succeeds(self, tmp_path):
        """Snakemake can plan the full local-example ingest DAG without errors."""
        resolved_config = _resolved_config_for_build(tmp_path, LOCAL_BUILD_CONFIG)
        output, rc = _dry_run(tmp_path, resolved_config, build_config=LOCAL_BUILD_CONFIG)
        assert rc == 0, (
            f"local-example snakemake dry-run exited with code {rc}.\n" f"Output:\n{output}"
        )

    def test_fetch_local_is_scheduled_not_pathoplexus_or_ncbi(self, tmp_path):
        """fetch_local must appear in the DAG; remote fetch rules must not."""
        resolved_config = _resolved_config_for_build(tmp_path, LOCAL_BUILD_CONFIG)
        output, rc = _dry_run(tmp_path, resolved_config, build_config=LOCAL_BUILD_CONFIG)
        assert rc == 0, f"local dry-run failed:\n{output}"

        assert "fetch_local" in output, (
            "fetch_local rule was not found in the dry-run output.\n" f"Output:\n{output}"
        )
        assert "fetch_pathoplexus" not in output, (
            "fetch_pathoplexus appeared in the local dry-run — should be fetch_local only.\n"
            f"Output:\n{output}"
        )
        assert "fetch_ncbi" not in output, (
            "fetch_ncbi appeared in the local dry-run — should be fetch_local only.\n"
            f"Output:\n{output}"
        )

    def test_flexpipe_curate_uses_local_build_config(self, tmp_path):
        """flexpipe-curate must receive the local-example build config path."""
        resolved_config = _resolved_config_for_build(tmp_path, LOCAL_BUILD_CONFIG)
        output, rc = _dry_run(tmp_path, resolved_config, build_config=LOCAL_BUILD_CONFIG)
        assert rc == 0, f"local dry-run failed:\n{output}"

        curate_lines = [ln for ln in output.splitlines() if "flexpipe-curate" in ln]
        assert curate_lines, "flexpipe-curate command not found in dry-run output"

        for line in curate_lines:
            assert str(LOCAL_BUILD_CONFIG) in line, (
                f"flexpipe-curate was not given the local build config path.\n"
                f"Line: {line!r}\n"
                f"Expected: {LOCAL_BUILD_CONFIG}"
            )
            assert "snakemake_resolved" not in line, (
                f"flexpipe-curate received the resolved config instead of the build config.\n"
                f"Line: {line!r}"
            )


# ---------------------------------------------------------------------------
# ViralQC mode wiring — skip and precomputed paths
# ---------------------------------------------------------------------------

VIRALQC_PRECOMPUTED_TSV = (
    REPO_ROOT / "builds" / "local-example" / "local_data" / "viralqc_precomputed.tsv"
)


def _local_config_with_viralqc_mode(tmp_path, mode: str, precomputed: str = "") -> "Path":
    """Return a resolved local-example config with a specific viralqc.mode."""
    resolved = _resolved_config_for_build(tmp_path, LOCAL_BUILD_CONFIG)
    raw = yaml.safe_load(resolved.read_text())
    raw.setdefault("viralqc", {})["mode"] = mode
    if precomputed:
        raw["viralqc"]["precomputed"] = precomputed
    with open(resolved, "w", encoding="utf-8") as fh:
        yaml.safe_dump(raw, fh, default_flow_style=False, sort_keys=False)
    return resolved


@pytest.mark.integration
class TestViralqcModesWiring:
    """Verify skip and precomputed ViralQC modes via dry-run DAG planning."""

    def test_skip_mode_dry_run_succeeds(self, tmp_path):
        """viralqc.mode=skip: DAG plans without scheduling vqc."""
        resolved = _local_config_with_viralqc_mode(tmp_path, "skip")
        output, rc = _dry_run(tmp_path, resolved, build_config=LOCAL_BUILD_CONFIG)
        assert rc == 0, f"skip mode dry-run failed:\n{output}"
        assert "viralqc" in output

    def test_skip_mode_does_not_invoke_vqc_binary(self, tmp_path):
        """viralqc.mode=skip: the vqc binary must not appear in the planned commands."""
        resolved = _local_config_with_viralqc_mode(tmp_path, "skip")
        output, rc = _dry_run(tmp_path, resolved, build_config=LOCAL_BUILD_CONFIG)
        assert rc == 0, f"skip mode dry-run failed:\n{output}"
        assert "vqc run" not in output
        assert "--datasets-dir" not in output

    def test_precomputed_mode_dry_run_succeeds(self, tmp_path):
        """viralqc.mode=precomputed: DAG plans with a cp rule, no vqc invocation."""
        resolved = _local_config_with_viralqc_mode(
            tmp_path, "precomputed", str(VIRALQC_PRECOMPUTED_TSV)
        )
        output, rc = _dry_run(tmp_path, resolved, build_config=LOCAL_BUILD_CONFIG)
        assert rc == 0, f"precomputed mode dry-run failed:\n{output}"
        assert "viralqc" in output
        assert "vqc run" not in output
        assert "--datasets-dir" not in output
