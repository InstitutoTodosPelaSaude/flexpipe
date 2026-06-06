"""Integration tests: Snakemake dry-run wiring for the ingest stage.

These tests invoke ``snakemake --dry-run --printshellcmds`` (no real data) to verify
two key wiring invariants that are hard to catch with unit tests alone:

1. ``flexpipe-curate`` and other flexpipe-* CLIs receive ``--config <build>/config.yaml``
   (the full build config), **never** the partial ``snakemake_resolved.yaml`` overrides.

2. The ``viralqc`` rule receives a non-empty ``--datasets-dir`` path, confirming that the
   resolved ViralQC paths written to ``snakemake_resolved.yaml`` by ``flexpipe-run`` are
   picked up by Snakemake params.

These tests use no real data, network access, or conda envs — just the Snakemake DAG
planner (dry-run mode).  They are tagged ``integration`` because they shell out to
``snakemake`` and therefore require the nextstrain environment to be active.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

# Repository root is three levels up from this file: tests/integration/ → tests/ → repo
REPO_ROOT = Path(__file__).parent.parent.parent
INGEST_SNAKEFILE = REPO_ROOT / "ingest" / "Snakefile"
BUILD_CONFIG = REPO_ROOT / "builds" / "yfv-brazil" / "config.yaml"

# Sentinel paths used in the fake overrides YAML; chosen to be distinctive and
# absolute so they appear verbatim in the rendered shell commands.
FAKE_DATASETS_DIR = "/fake/viralqc/datasets"
FAKE_BLAST_DB = "/fake/viralqc/datasets/blast.fasta"
FAKE_BLAST_META = "/fake/viralqc/datasets/blast.tsv"


@pytest.fixture()
def overrides_yaml(tmp_path):
    """Write a fake snakemake_resolved.yaml with non-empty ViralQC paths."""
    data = {
        "viralqc": {
            "conda_env": "viralQC",
            "clade_column": "clade",
            "datasets_dir": FAKE_DATASETS_DIR,
            "blast_database": FAKE_BLAST_DB,
            "blast_database_metadata": FAKE_BLAST_META,
            "expected_virus": None,
        }
    }
    p = tmp_path / "snakemake_resolved.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def _dry_run(tmp_path, overrides_yaml, extra_config=None):
    """Run ``snakemake -n -p`` on the ingest Snakefile and return captured output.

    Returns:
        Combined stdout + stderr string.

    Raises:
        pytest.skip if snakemake is not found on PATH.
    """
    if not shutil.which("snakemake"):
        pytest.skip("snakemake not found on PATH — activate the nextstrain conda env")

    workdir = tmp_path / "workdir"
    cmd = [
        "snakemake",
        "--snakefile", str(INGEST_SNAKEFILE),
        "--configfile", str(BUILD_CONFIG),
        "--configfile", str(overrides_yaml),
        "--config",
        f"workdir={workdir}",
        f"build_config={BUILD_CONFIG}",
        "--dry-run",
        "--printshellcmds",
        "--cores", "1",
        "--nolock",
    ]
    if extra_config:
        cmd.extend(extra_config)

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
    def test_dry_run_succeeds(self, tmp_path, overrides_yaml):
        """Snakemake can plan the full ingest DAG without errors."""
        output, rc = _dry_run(tmp_path, overrides_yaml)
        assert rc == 0, (
            f"snakemake dry-run exited with code {rc}.\n"
            f"Output:\n{output}"
        )

    def test_flexpipe_curate_uses_build_config_not_overrides(self, tmp_path, overrides_yaml):
        """flexpipe-curate must receive the build config path, not snakemake_resolved.yaml."""
        output, rc = _dry_run(tmp_path, overrides_yaml)
        assert rc == 0, f"dry-run failed:\n{output}"

        # Find the flexpipe-curate invocation in the rendered commands
        curate_lines = [ln for ln in output.splitlines() if "flexpipe-curate" in ln]
        assert curate_lines, "flexpipe-curate command not found in dry-run output"

        for line in curate_lines:
            assert str(BUILD_CONFIG) in line, (
                f"flexpipe-curate was not given the build config path.\n"
                f"Line: {line!r}\n"
                f"Expected: {BUILD_CONFIG}"
            )
            assert "snakemake_resolved.yaml" not in line, (
                f"flexpipe-curate received the overrides file instead of the build config.\n"
                f"Line: {line!r}"
            )

    def test_viralqc_rule_has_non_empty_datasets_dir(self, tmp_path, overrides_yaml):
        """The viralqc rule must use the resolved --datasets-dir, not an empty string."""
        output, rc = _dry_run(tmp_path, overrides_yaml)
        assert rc == 0, f"dry-run failed:\n{output}"

        # Find the vqc run invocation
        vqc_lines = [ln for ln in output.splitlines() if "vqc run" in ln or "--datasets-dir" in ln]
        assert vqc_lines, "vqc run command not found in dry-run output"

        for line in vqc_lines:
            if "--datasets-dir" in line:
                # Ensure it's not an empty/blank value
                idx = line.find("--datasets-dir")
                remainder = line[idx + len("--datasets-dir"):].strip()
                assert remainder and not remainder.startswith("--"), (
                    f"--datasets-dir is empty or missing its argument.\nLine: {line!r}"
                )
                # Confirm the fake resolved path from overrides is present
                assert FAKE_DATASETS_DIR in line, (
                    f"Expected fake datasets dir {FAKE_DATASETS_DIR!r} in viralqc command.\n"
                    f"Line: {line!r}"
                )
