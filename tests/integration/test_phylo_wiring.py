"""Integration tests: Snakemake dry-run wiring for the phylogenetic stage."""

import shutil
import subprocess
from pathlib import Path

import pytest

from flexpipe.config import load_config, write_snakemake_config_overrides

REPO_ROOT = Path(__file__).parent.parent.parent
PHYLO_SNAKEFILE = REPO_ROOT / "phylogenetic" / "Snakefile"
YFV_BUILD_CONFIG = REPO_ROOT / "builds" / "yfv-brazil" / "config.yaml"
RSV_BUILD_CONFIG = REPO_ROOT / "builds" / "rsv-global" / "config.yaml"
DENV_BUILD_CONFIGS = [
    REPO_ROOT / "builds" / "denv1-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "denv2-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "denv3-brazil" / "config.yaml",
    REPO_ROOT / "builds" / "denv4-brazil" / "config.yaml",
]


def _seed_phylo_inputs(workdir: Path) -> None:
    """Create the static ingest outputs the phylogenetic dry-run expects."""
    subsampled = workdir / "results" / "subsampled"
    config_dir = workdir / "config"
    subsampled.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (subsampled / "sequences.fasta").write_text(">seq1\nACGT\n>seq2\nACGT\n")
    (subsampled / "metadata.tsv").write_text(
        "strain\tdate\tcontinent\tcountry\tdivision\tlocation\tclade\tclade_truncated\t"
        "serotype\tgenotype\tmajor_lineage\tminor_lineage\tregion\tsource\tdata_use\n"
        "seq1\t2025-01-01\tSouth America\tBrazil\tSao Paulo\tSao Paulo\t3III_B.3.2\t"
        "3III_B.3.2\t3\t3III\t3III_B\t3III_B.3.2\tSudeste\tPathoplexus\tOPEN\n"
        "seq2\t2025-01-02\tSouth America\tBrazil\tRio de Janeiro\tRio de Janeiro\t3III_B.3.2\t"
        "3III_B.3.2\t3\t3III\t3III_B\t3III_B.3.2\tSudeste\tPathoplexus\tOPEN\n"
    )
    (config_dir / "latlongs.tsv").write_text("country\tBrazil\t-14.235\t-51.9253\n")
    (config_dir / "colour_scheme.tsv").write_text("trait\tvalue\tdisplay_name\tcolor\n")


def _resolved_config(build_config: Path, workdir: Path, monkeypatch) -> Path:
    """Write a workdir-local resolved config for *build_config*."""
    monkeypatch.setenv("NCBI_EMAIL", "ops@example.org")
    cfg = load_config(build_config, workdir=workdir, skip_viralqc=True)
    return write_snakemake_config_overrides(
        cfg, workdir / "config" / "snakemake_resolved.yaml", build_config
    )


def _dry_run(tmp_path, build_config: Path, monkeypatch, workdir_name: str = "workdir"):
    if not shutil.which("snakemake"):
        pytest.skip("snakemake not found on PATH — activate the nextstrain conda env")

    workdir = tmp_path / workdir_name
    outside = tmp_path / "outside"
    outside.mkdir()
    _seed_phylo_inputs(workdir)
    resolved = _resolved_config(build_config, workdir, monkeypatch)

    cmd = [
        "snakemake",
        "--snakefile",
        str(PHYLO_SNAKEFILE),
        "--configfile",
        str(resolved),
        "--config",
        f"workdir={workdir}",
        f"build_config={build_config}",
        "--dry-run",
        "--printshellcmds",
        "--cores",
        "1",
        "--nolock",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=outside)
    return result.stdout + "\n" + result.stderr, result.returncode


def _mask_command(output: str) -> str:
    lines = output.splitlines()
    for idx, line in enumerate(lines):
        if "augur mask" in line:
            return "\n".join(lines[idx : idx + 8])
    return ""


@pytest.mark.integration
class TestPhyloWiring:
    def test_yfv_dry_run_from_outside_repo_renders_mask_sites(self, tmp_path, monkeypatch):
        output, rc = _dry_run(tmp_path, YFV_BUILD_CONFIG, monkeypatch)
        assert rc == 0, f"YFV phylo dry-run failed:\n{output}"
        mask_cmd = _mask_command(output)
        assert "augur mask" in mask_cmd
        assert "--mask-sites 1" in mask_cmd
        assert str(REPO_ROOT / "builds" / "yfv-brazil" / "reference.gb") in output
        assert str(REPO_ROOT / "builds" / "yfv-brazil" / "clades.tsv") in output
        assert str(REPO_ROOT / "builds" / "yfv-brazil" / "auspice_config.json") in output
        assert "flexpipe-collapse-traits" in output
        assert "metadata_traits.tsv" in output
        assert "--columns          continent country division location clade" in output
        assert "-m     MFP" in output
        assert "-B 1000" in output
        assert "--date-confidence" in output
        assert "--confidence" in output

    def test_rsv_dry_run_from_outside_repo_omits_empty_mask_sites(self, tmp_path, monkeypatch):
        output, rc = _dry_run(tmp_path, RSV_BUILD_CONFIG, monkeypatch)
        assert rc == 0, f"RSV phylo dry-run failed:\n{output}"
        assert "augur mask" not in output
        assert "cp " in output
        assert str(REPO_ROOT / "builds" / "rsv-global" / "reference.gb") in output
        assert str(REPO_ROOT / "builds" / "rsv-global" / "clades.tsv") in output
        assert str(REPO_ROOT / "builds" / "rsv-global" / "auspice_config.json") in output

    def test_threads_are_capped_by_snakemake_cores(self, tmp_path, monkeypatch):
        output, rc = _dry_run(tmp_path, YFV_BUILD_CONFIG, monkeypatch)
        assert rc == 0, f"YFV phylo dry-run failed:\n{output}"
        assert "--nthreads           1" in output
        assert "-T     1" in output
        assert "--threads-max 1" in output

    def test_paths_with_spaces_survive_dry_run_rendering(self, tmp_path, monkeypatch):
        output, rc = _dry_run(tmp_path, YFV_BUILD_CONFIG, monkeypatch, "work dir with spaces")
        assert rc == 0, f"YFV phylo dry-run with spaced workdir failed:\n{output}"
        assert "work dir with spaces" in output

    @pytest.mark.parametrize("build_config", DENV_BUILD_CONFIGS, ids=lambda p: p.parent.name)
    def test_denv_phylo_dry_run_when_reference_is_real(self, tmp_path, monkeypatch, build_config):
        """DENV phylo dry-runs are deferred while reference.gb is an intentional placeholder."""
        reference = build_config.parent / "reference.gb"
        if "PLACEHOLDER" in reference.read_text():
            pytest.skip(f"{build_config.parent.name} reference.gb is still a placeholder")

        output, rc = _dry_run(tmp_path, build_config, monkeypatch)
        assert rc == 0, f"{build_config.parent.name} phylo dry-run failed:\n{output}"
        assert str(reference) in output
        assert "flexpipe-collapse-traits" in output
        assert "metadata_traits.tsv" in output
        assert "--max-states       200" in output
        assert "--rare-state-label other" in output
        assert (
            "--columns          continent country division location serotype genotype major_lineage minor_lineage clade"
            in output
        )
        assert "augur mask" not in output
        assert "cp " in output
        assert "-m     JC" in output
        assert "-B " not in output
        assert "--date-confidence" not in output
        assert "--confidence" not in output
