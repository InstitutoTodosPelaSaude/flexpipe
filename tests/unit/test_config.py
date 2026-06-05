"""Unit tests for flexpipe.config — FlexpipeConfig pydantic model."""

import pytest
from pathlib import Path

import pydantic

from flexpipe.config import (
    FlexpipeConfig,
    FilesConfig,
    ParametersConfig,
    ColoursConfig,
    ColoursHueTablesConfig,
    RegionsConfig,
    CurationConfig,
    PathsConfig,
    ViralqcConfig,
    load_config,
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
