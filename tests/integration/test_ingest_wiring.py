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

from flexpipe.config import FlexpipeConfig, ViralqcConfig, write_snakemake_config_overrides

# Repository root is three levels up from this file: tests/integration/ → tests/ → repo
REPO_ROOT = Path(__file__).parent.parent.parent
INGEST_SNAKEFILE = REPO_ROOT / "ingest" / "Snakefile"
BUILD_CONFIG = REPO_ROOT / "builds" / "yfv-brazil" / "config.yaml"
RSV_BUILD_CONFIG = REPO_ROOT / "builds" / "rsv-global" / "config.yaml"

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


def _dry_run(tmp_path, resolved_config, build_config=None):
    """Run ``snakemake -n -p`` on the ingest Snakefile and return captured output.

    Args:
        build_config: Path to the build config.yaml passed as ``build_config``
            Snakemake config key.  Defaults to the YFV-Brazil config.

    Returns:
        (combined_output, return_code)

    Raises:
        pytest.skip if snakemake is not found on PATH.
    """
    if not shutil.which("snakemake"):
        pytest.skip("snakemake not found on PATH — activate the nextstrain conda env")

    if build_config is None:
        build_config = BUILD_CONFIG

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
        cwd=REPO_ROOT,
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


@pytest.mark.integration
class TestIngestWiring:
    def test_dry_run_succeeds(self, tmp_path, resolved_config):
        """Snakemake can plan the full ingest DAG without errors."""
        output, rc = _dry_run(tmp_path, resolved_config)
        assert rc == 0, f"snakemake dry-run exited with code {rc}.\n" f"Output:\n{output}"

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

    def test_dry_run_with_run_date_schedules_resolve_subsample_config(
        self, tmp_path, resolved_config
    ):
        """Passing run_date causes the resolve_subsample_config rule to be scheduled."""
        output, rc = _dry_run_with_run_date(tmp_path, resolved_config, "2026-01-01")
        assert rc == 0, f"dry-run with run_date failed:\n{output}"
        assert "resolve_subsample_config" in output, (
            "resolve_subsample_config rule was not scheduled.\n" f"Output:\n{output}"
        )

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
        ncbi={"taxid": 208893, "genome_size": 15200},
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
