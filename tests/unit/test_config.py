"""Unit tests for flexpipe.config — FlexpipeConfig pydantic model."""

from pathlib import Path

import pydantic
import pytest

from flexpipe.config import (
    FlexpipeConfig,
    ViralqcConfig,
    load_config,
    resolve_viralqc_paths,
)

# ---------------------------------------------------------------------------
# Default construction
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_empty_config_uses_defaults(self):
        # data_source defaults to "pathoplexus" but organism defaults to ""
        # which would fail the cross-field validator; supply the minimum viable config
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
        )
        assert cfg.data_source == "pathoplexus"
        assert cfg.region_source == "country"
        assert cfg.parameters.ufboot == 1000
        assert cfg.options.threads == 4
        assert cfg.subsampling.random_seed == 42
        assert cfg.curation.clade_levels == 1
        assert cfg.paths.workdir == "workdir"

    def test_ncbi_source_defaults(self):
        cfg = FlexpipeConfig(
            data_source="ncbi",
            ncbi={"taxid": 11089, "genome_size": 10862},
        )
        assert cfg.data_source == "ncbi"
        assert cfg.ncbi.taxid == 11089

    def test_colours_defaults(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
        )
        assert cfg.colours.clade == "clade_truncated clade"
        assert cfg.colours.geo == "region division location"
        assert cfg.colours.hue_tables.region is None

    def test_qc_defaults(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
        )
        assert cfg.qc.genome_quality == ["A", "B"]
        assert cfg.qc.min_coverage == pytest.approx(0.70)

    def test_files_defaults(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
        )
        assert cfg.files.keep == "config/keep.txt"
        assert cfg.files.clades == "config/clades.tsv"

    def test_regions_defaults(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
        )
        assert cfg.regions.country_map is None
        assert cfg.regions.division_parser == "brazil"


# ---------------------------------------------------------------------------
# Cross-field validators
# ---------------------------------------------------------------------------


class TestCrossFieldValidators:
    def test_pathoplexus_missing_organism_raises(self):
        with pytest.raises(pydantic.ValidationError, match="pathoplexus.organism"):
            FlexpipeConfig(data_source="pathoplexus", pathoplexus={"organism": ""})

    def test_ncbi_missing_taxid_raises(self):
        with pytest.raises(pydantic.ValidationError, match="ncbi.taxid"):
            FlexpipeConfig(data_source="ncbi", ncbi={"taxid": 0})

    def test_invalid_data_source_raises(self):
        with pytest.raises(pydantic.ValidationError):
            FlexpipeConfig(
                data_source="gisaid",
                pathoplexus={"organism": "yellow-fever"},
            )

    def test_invalid_region_source_raises(self):
        with pytest.raises(pydantic.ValidationError):
            FlexpipeConfig(
                data_source="pathoplexus",
                pathoplexus={"organism": "yellow-fever"},
                region_source="state",
            )

    def test_nonexistent_country_map_override_raises(self, tmp_path):
        with pytest.raises(pydantic.ValidationError, match="regions.country_map"):
            FlexpipeConfig(
                data_source="pathoplexus",
                pathoplexus={"organism": "yellow-fever"},
                regions={"country_map": str(tmp_path / "nonexistent.tsv")},
            )

    def test_existing_country_map_override_accepted(self, tmp_path):
        override = tmp_path / "country_map.tsv"
        override.write_text("country\tcontinent\nBrazil\tSouth America\n")
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            regions={"country_map": str(override)},
        )
        assert cfg.regions.country_map == str(override)

    def test_nonexistent_hue_table_override_raises(self, tmp_path):
        with pytest.raises(pydantic.ValidationError, match="colours.hue_tables.region"):
            FlexpipeConfig(
                data_source="pathoplexus",
                pathoplexus={"organism": "yellow-fever"},
                colours={"hue_tables": {"region": str(tmp_path / "nope.tsv")}},
            )

    def test_existing_hue_table_override_accepted(self, tmp_path):
        override = tmp_path / "region_hues.tsv"
        override.write_text("category\thue\nNordeste\t30\n")
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            colours={"hue_tables": {"region": str(override)}},
        )
        assert cfg.colours.hue_tables.region == str(override)


# ---------------------------------------------------------------------------
# load_config() with fixture YAML
# ---------------------------------------------------------------------------


@pytest.fixture
def yfv_config_path():
    return Path(__file__).parent.parent / "fixtures" / "config_division_build.yaml"


class TestLoadConfig:
    def test_load_division_config(self, yfv_config_path):
        cfg = load_config(yfv_config_path, workdir="/tmp/testrun", skip_viralqc=True)
        assert isinstance(cfg, FlexpipeConfig)
        assert cfg.region_source == "division"
        assert cfg.data_source == "pathoplexus"

    def test_workdir_override_takes_precedence(self, yfv_config_path):
        cfg = load_config(yfv_config_path, workdir="/tmp/override", skip_viralqc=True)
        assert cfg.paths.workdir == "/tmp/override"

    def test_extra_fields_allowed(self, tmp_path):
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "some_future_key: some_value\n"
        )
        cfg = load_config(config_yaml, skip_viralqc=True)
        assert cfg.data_source == "pathoplexus"

    def test_paths_workdir_from_yaml(self, tmp_path):
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "paths:\n  workdir: /tmp/from_yaml\n"
        )
        cfg = load_config(config_yaml, skip_viralqc=True)
        assert cfg.paths.workdir == "/tmp/from_yaml"

    def test_workdir_arg_overrides_yaml(self, tmp_path):
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "paths:\n  workdir: /tmp/from_yaml\n"
        )
        cfg = load_config(config_yaml, workdir="/tmp/from_arg", skip_viralqc=True)
        assert cfg.paths.workdir == "/tmp/from_arg"


# ---------------------------------------------------------------------------
# ViralqcConfig standalone
# ---------------------------------------------------------------------------


class TestViralqcConfig:
    def test_default_fields(self):
        v = ViralqcConfig()
        assert v.conda_env == "viralQC"
        assert v.clade_column == "clade"
        assert v.datasets_dir == ""

    def test_model_dump_round_trip(self):
        v = ViralqcConfig(datasets_dir="/data/vqc", blast_database="/data/vqc/blast.fasta")
        d = v.model_dump()
        assert d["datasets_dir"] == "/data/vqc"
        v2 = ViralqcConfig(**d)
        assert v2.blast_database == "/data/vqc/blast.fasta"


# ---------------------------------------------------------------------------
# resolve_viralqc_paths — datasets_dir resolution order
# ---------------------------------------------------------------------------


class TestResolveViralqcPaths:
    """Tests for the three-step resolution: config key → env var → submodule fallback."""

    def _make_fake_datasets(self, tmp_path: Path) -> Path:
        """Create a minimal fake datasets directory with the expected blast files."""
        d = tmp_path / "datasets"
        d.mkdir()
        (d / "blast.fasta").write_text(">seq1\nATCG\n")
        (d / "blast.tsv").write_text("accession\torganism\nNC_001\tyellow-fever\n")
        return d

    def test_explicit_config_key_wins(self, tmp_path, monkeypatch):
        """viralqc.datasets_dir in config takes highest precedence."""
        ds = self._make_fake_datasets(tmp_path)
        monkeypatch.delenv("VIRALQC_DATASETS_DIR", raising=False)
        v = resolve_viralqc_paths(ViralqcConfig(datasets_dir=str(ds)))
        assert v.datasets_dir == str(ds)
        assert v.blast_database == str(ds / "blast.fasta")
        assert v.blast_database_metadata == str(ds / "blast.tsv")

    def test_env_var_wins_over_submodule(self, tmp_path, monkeypatch):
        """$VIRALQC_DATASETS_DIR overrides the submodule fallback."""
        ds = self._make_fake_datasets(tmp_path)
        # Simulate submodule datasets present at a *different* path
        fake_submodule = tmp_path / "fake_repo" / "viralQC" / "datasets"
        fake_submodule.mkdir(parents=True)
        (fake_submodule / "blast.fasta").write_text(">should_not_use\n")
        (fake_submodule / "blast.tsv").write_text("")
        monkeypatch.setenv("VIRALQC_DATASETS_DIR", str(ds))
        v = resolve_viralqc_paths(ViralqcConfig(datasets_dir=""))
        assert v.datasets_dir == str(ds)

    def test_submodule_fallback_used_when_nothing_else_set(self, tmp_path, monkeypatch):
        """Auto-discovers viralQC/datasets relative to the package when it exists."""
        import flexpipe.config as cfg_module

        monkeypatch.delenv("VIRALQC_DATASETS_DIR", raising=False)
        # Patch __file__ of the config module to point inside our tmp_path tree so
        # parents[1] / "viralQC" / "datasets" resolves to our fake datasets dir.
        fake_config_py = tmp_path / "flexpipe" / "config.py"
        fake_config_py.parent.mkdir(parents=True)
        fake_config_py.write_text("")
        # The submodule fallback computes: Path(__file__).resolve().parents[1] / "viralQC" / "datasets"
        # parents[1] of <tmp>/flexpipe/config.py  →  <tmp>
        # <tmp>/viralQC/datasets  →  ds (which is tmp_path/datasets — we need to move it)
        viralqc_datasets = tmp_path / "viralQC" / "datasets"
        viralqc_datasets.mkdir(parents=True)
        (viralqc_datasets / "blast.fasta").write_text(">seq\nATCG\n")
        (viralqc_datasets / "blast.tsv").write_text("accession\torganism\n")
        monkeypatch.setattr(cfg_module, "__file__", str(fake_config_py))
        v = resolve_viralqc_paths(ViralqcConfig(datasets_dir=""))
        assert str(viralqc_datasets) in v.datasets_dir

    def test_no_config_no_env_no_submodule_raises(self, monkeypatch):
        """SystemExit with a helpful message when nothing resolves."""
        import flexpipe.config as cfg_module

        monkeypatch.delenv("VIRALQC_DATASETS_DIR", raising=False)
        # Point __file__ to a dir where viralQC/datasets does not exist
        monkeypatch.setattr(cfg_module, "__file__", "/nonexistent/path/flexpipe/config.py")
        with pytest.raises(SystemExit, match="install_viralqc.sh"):
            resolve_viralqc_paths(ViralqcConfig(datasets_dir=""))

    def test_explicit_blast_paths_not_overridden(self, tmp_path, monkeypatch):
        """Explicit blast_database / blast_database_metadata survive resolution."""
        ds = self._make_fake_datasets(tmp_path)
        custom_blast = tmp_path / "custom.fasta"
        custom_blast.write_text(">x\nA\n")
        monkeypatch.delenv("VIRALQC_DATASETS_DIR", raising=False)
        v = resolve_viralqc_paths(
            ViralqcConfig(
                datasets_dir=str(ds),
                blast_database=str(custom_blast),
            )
        )
        assert v.blast_database == str(custom_blast)
