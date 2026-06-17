"""Unit tests for flexpipe.config — FlexpipeConfig pydantic model."""

from pathlib import Path

import pydantic
import pytest
import yaml

from flexpipe.config import (
    FlexpipeConfig,
    ViralqcConfig,
    load_config,
    resolve_subsample_config,
    resolve_viralqc_paths,
    write_snakemake_config_overrides,
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
        assert cfg.subsampling.backbone_strains is None
        assert cfg.curation.clade_levels == 1
        assert cfg.curation.lineage_parser == "none"
        assert cfg.curation.lineage_columns.genotype == "genotype"
        assert cfg.traits.max_states == 200
        assert cfg.traits.rare_state_label == "other"
        assert cfg.paths.workdir == "workdir"

    def test_ncbi_source_defaults(self):
        cfg = FlexpipeConfig(
            data_source="ncbi",
            ncbi={"taxid": 11089, "genome_size": 10862, "email": "ops@example.org"},
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
            FlexpipeConfig(data_source="ncbi", ncbi={"taxid": 0, "email": "ops@example.org"})

    def test_ncbi_missing_email_raises(self, monkeypatch):
        monkeypatch.delenv("NCBI_EMAIL", raising=False)
        with pytest.raises(pydantic.ValidationError, match="ncbi.email"):
            FlexpipeConfig(
                data_source="ncbi",
                ncbi={"taxid": 11089, "genome_size": 10862},
            )

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
    def _make_fake_datasets(self, tmp_path: Path) -> Path:
        datasets = tmp_path / "datasets"
        datasets.mkdir()
        (datasets / "blast.fasta").write_text(">seq1\nATCG\n")
        (datasets / "blast.tsv").write_text("accession\torganism\nNC_001\tyellow-fever\n")
        return datasets

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

    def test_run_mode_preflight_applies_when_viralqc_section_is_omitted(
        self, tmp_path, monkeypatch
    ):
        datasets = self._make_fake_datasets(tmp_path)
        monkeypatch.setenv("VIRALQC_DATASETS_DIR", str(datasets))
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n" "pathoplexus:\n  organism: yellow-fever\n"
        )

        cfg = load_config(config_yaml)

        assert cfg.viralqc.mode == "run"
        assert cfg.viralqc.datasets_dir == str(datasets)
        assert cfg.viralqc.blast_database == str(datasets / "blast.fasta")

    def test_run_mode_without_viralqc_section_still_requires_datasets(self, tmp_path, monkeypatch):
        import flexpipe.config as cfg_module

        monkeypatch.delenv("VIRALQC_DATASETS_DIR", raising=False)
        monkeypatch.setattr(cfg_module, "__file__", "/nonexistent/path/flexpipe/config.py")
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n" "pathoplexus:\n  organism: yellow-fever\n"
        )

        with pytest.raises(SystemExit, match="ViralQC datasets directory not configured"):
            load_config(config_yaml)

    def test_skip_mode_does_not_require_viralqc_datasets(self, tmp_path, monkeypatch):
        import flexpipe.config as cfg_module

        monkeypatch.delenv("VIRALQC_DATASETS_DIR", raising=False)
        monkeypatch.setattr(cfg_module, "__file__", "/nonexistent/path/flexpipe/config.py")
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "viralqc:\n  mode: skip\n"
        )

        cfg = load_config(config_yaml)

        assert cfg.viralqc.mode == "skip"
        assert cfg.viralqc.datasets_dir == ""

    def test_precomputed_mode_does_not_require_viralqc_datasets(self, tmp_path, monkeypatch):
        import flexpipe.config as cfg_module

        monkeypatch.delenv("VIRALQC_DATASETS_DIR", raising=False)
        monkeypatch.setattr(cfg_module, "__file__", "/nonexistent/path/flexpipe/config.py")
        precomputed = tmp_path / "results.tsv"
        precomputed.write_text("strain\tgenome_quality\tcoverage\tclade\n")
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "viralqc:\n"
            "  mode: precomputed\n"
            "  precomputed: results.tsv\n"
        )

        cfg = load_config(config_yaml)

        assert cfg.viralqc.mode == "precomputed"
        assert cfg.viralqc.precomputed == str(precomputed)
        assert cfg.viralqc.datasets_dir == ""

    def test_build_relative_paths_resolve_from_config_dir(self, tmp_path, monkeypatch):
        build = tmp_path / "build"
        build.mkdir()
        for filename in [
            "keep.txt",
            "ignore.txt",
            "reference.gb",
            "clades.tsv",
            "auspice_config.json",
            "subsample.yaml",
            "mask.bed",
            "force.tsv",
            "country.tsv",
            "host_rules.yaml",
            "region_hues.tsv",
        ]:
            (build / filename).write_text("x\n")
        config_yaml = build / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "files:\n"
            "  keep: keep.txt\n"
            "  ignore: ignore.txt\n"
            "  cache: cache_coordinates.tsv\n"
            "  reference: reference.gb\n"
            "  clades: clades.tsv\n"
            "  auspice_config: auspice_config.json\n"
            "  subsample_config: subsample.yaml\n"
            "parameters:\n"
            "  mask_sites_file: mask.bed\n"
            "coordinates:\n"
            "  columns: country\n"
            "  force_file: force.tsv\n"
            "regions:\n"
            "  country_map: country.tsv\n"
            "curation:\n"
            "  host_rules: host_rules.yaml\n"
            "colours:\n"
            "  hue_tables:\n"
            "    region: region_hues.tsv\n"
        )
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.chdir(outside)

        cfg = load_config(config_yaml, skip_viralqc=True)

        assert cfg.files.reference == str(build / "reference.gb")
        assert cfg.files.subsample_config == str(build / "subsample.yaml")
        assert cfg.files.cache == str(build / "cache_coordinates.tsv")
        assert cfg.parameters.mask_sites_file == str(build / "mask.bed")
        assert cfg.coordinates.force_file == str(build / "force.tsv")
        assert cfg.regions.country_map == str(build / "country.tsv")
        assert cfg.curation.host_rules == str(build / "host_rules.yaml")
        assert cfg.colours.hue_tables.region == str(build / "region_hues.tsv")

    def test_local_sequence_paths_required_only_when_enabled(self, tmp_path):
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "local_sequences:\n"
            "  enabled: false\n"
            "  metadata: missing.tsv\n"
            "  sequences: missing.fasta\n"
        )
        cfg = load_config(config_yaml, skip_viralqc=True)
        assert cfg.local_sequences.enabled is False

        config_yaml.write_text(
            "data_source: pathoplexus\n"
            "pathoplexus:\n  organism: yellow-fever\n"
            "local_sequences:\n"
            "  enabled: true\n"
            "  metadata: missing.tsv\n"
            "  sequences: missing.fasta\n"
        )
        with pytest.raises(SystemExit, match="local_sequences.metadata"):
            load_config(config_yaml, skip_viralqc=True)

    def test_invalid_enum_and_column_list_fail_fast(self):
        with pytest.raises(pydantic.ValidationError, match="parameters.root"):
            FlexpipeConfig(
                data_source="pathoplexus",
                pathoplexus={"organism": "yellow-fever"},
                parameters={"root": "bad-root"},
            )

        with pytest.raises(pydantic.ValidationError, match="traits.columns"):
            FlexpipeConfig(
                data_source="pathoplexus",
                pathoplexus={"organism": "yellow-fever"},
                traits={"columns": "division; rm -rf"},
            )

        with pytest.raises(pydantic.ValidationError, match="curation.lineage_parser"):
            FlexpipeConfig(
                data_source="pathoplexus",
                pathoplexus={"organism": "yellow-fever"},
                curation={"lineage_parser": "invented"},
            )

        with pytest.raises(pydantic.ValidationError, match="lineage column names"):
            FlexpipeConfig(
                data_source="pathoplexus",
                pathoplexus={"organism": "yellow-fever"},
                curation={"lineage_columns": {"genotype": "bad name"}},
            )

    def test_resolve_subsample_paths_makes_includes_absolute(self, tmp_path):
        build = tmp_path / "build"
        build.mkdir()
        for filename in ["default_exclude.txt", "include.txt", "exclude.txt"]:
            (build / filename).write_text("seq1\n")
        subsample_yaml = build / "subsample.yaml"
        raw = {
            "defaults": {"exclude": "default_exclude.txt"},
            "samples": {
                "focal": {"include": "include.txt", "exclude": ["exclude.txt"]},
                "context": {"exclude_where": "region=Europe"},
            },
        }

        resolved = resolve_subsample_config(raw, "2026-01-01", subsample_yaml)

        assert resolved["defaults"]["exclude"] == str(build / "default_exclude.txt")
        assert resolved["samples"]["focal"]["include"] == str(build / "include.txt")
        assert resolved["samples"]["focal"]["exclude"] == [str(build / "exclude.txt")]
        assert resolved["samples"]["context"]["exclude_where"] == "region=Europe"
        assert resolved["defaults"]["max_date"] == "2026-01-01"


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


# ---------------------------------------------------------------------------
# write_snakemake_config_overrides
# ---------------------------------------------------------------------------


FIXTURE_CONFIG = Path(__file__).parent.parent / "fixtures" / "config_division_build.yaml"
REPO_ROOT = Path(__file__).parent.parent.parent
YFV_BUILD_CONFIG = REPO_ROOT / "builds" / "yfv-brazil" / "config.yaml"


class TestWriteSnakemakeConfigOverrides:
    def test_writes_resolved_viralqc_paths(self, tmp_path):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            viralqc=ViralqcConfig(
                datasets_dir="/data/viralQC/datasets",
                blast_database="/data/viralQC/datasets/blast.fasta",
                blast_database_metadata="/data/viralQC/datasets/blast.tsv",
            ),
        )
        out = write_snakemake_config_overrides(
            cfg, tmp_path / "snakemake_resolved.yaml", FIXTURE_CONFIG
        )
        assert out.exists()
        loaded = yaml.safe_load(out.read_text())
        assert loaded["viralqc"]["datasets_dir"] == "/data/viralQC/datasets"
        assert loaded["viralqc"]["blast_database"] == "/data/viralQC/datasets/blast.fasta"
        assert loaded["viralqc"]["blast_database_metadata"] == "/data/viralQC/datasets/blast.tsv"

    def test_preserves_all_build_config_keys(self, tmp_path):
        """Full build config is written, not just viralqc — Snakemake needs everything."""
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            viralqc=ViralqcConfig(
                datasets_dir="/data/viralQC/datasets",
                blast_database="/data/viralQC/datasets/blast.fasta",
                blast_database_metadata="/data/viralQC/datasets/blast.tsv",
            ),
        )
        out = write_snakemake_config_overrides(
            cfg, tmp_path / "snakemake_resolved.yaml", FIXTURE_CONFIG
        )
        loaded = yaml.safe_load(out.read_text())
        # All top-level keys from the fixture config must be present
        fixture_keys = yaml.safe_load(FIXTURE_CONFIG.read_text()).keys()
        for key in fixture_keys:
            assert key in loaded, f"Key '{key}' from build config missing in resolved YAML"

    def test_writes_absolute_build_paths(self, tmp_path):
        cfg = load_config(YFV_BUILD_CONFIG, workdir=tmp_path / "workdir", skip_viralqc=True)
        out = write_snakemake_config_overrides(
            cfg, tmp_path / "snakemake_resolved.yaml", YFV_BUILD_CONFIG
        )
        loaded = yaml.safe_load(out.read_text())
        assert Path(loaded["files"]["reference"]).is_absolute()
        assert Path(loaded["files"]["clades"]).is_absolute()
        assert Path(loaded["files"]["auspice_config"]).is_absolute()
        assert Path(loaded["files"]["subsample_config"]).is_absolute()

    def test_backbone_strains_default_none_in_resolved_yaml(self, tmp_path):
        """backbone_strains defaults to None and propagates into the resolved YAML."""
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            viralqc=ViralqcConfig(
                datasets_dir="/data/viralQC/datasets",
                blast_database="/data/viralQC/datasets/blast.fasta",
                blast_database_metadata="/data/viralQC/datasets/blast.tsv",
            ),
        )
        assert cfg.subsampling.backbone_strains is None
        out = write_snakemake_config_overrides(
            cfg, tmp_path / "snakemake_resolved.yaml", FIXTURE_CONFIG
        )
        loaded = yaml.safe_load(out.read_text())
        assert loaded["subsampling"]["backbone_strains"] is None

    def test_backbone_strains_set_in_resolved_yaml(self, tmp_path):
        """When backbone_strains is set on the config, it propagates into the resolved YAML."""
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            viralqc=ViralqcConfig(
                datasets_dir="/data/viralQC/datasets",
                blast_database="/data/viralQC/datasets/blast.fasta",
                blast_database_metadata="/data/viralQC/datasets/blast.tsv",
            ),
        )
        cfg.subsampling.backbone_strains = "/tmp/workdir/config/backbone_strains.txt"
        out = write_snakemake_config_overrides(
            cfg, tmp_path / "snakemake_resolved.yaml", FIXTURE_CONFIG
        )
        loaded = yaml.safe_load(out.read_text())
        assert (
            loaded["subsampling"]["backbone_strains"] == "/tmp/workdir/config/backbone_strains.txt"
        )


# ---------------------------------------------------------------------------
# 5.6 — ViralqcConfig.expected_segment
# ---------------------------------------------------------------------------


class TestViralqcExpectedSegment:
    """expected_segment field closes the extra="forbid" gap in ViralqcConfig."""

    def test_default_is_empty_string(self):
        cfg = ViralqcConfig()
        assert cfg.expected_segment == ""

    def test_valid_segment_accepted(self):
        cfg = ViralqcConfig(expected_segment="L")
        assert cfg.expected_segment == "L"

    def test_aliases_file_is_accepted(self):
        cfg = ViralqcConfig(aliases_file="/tmp/aliases.yaml")
        assert cfg.aliases_file == "/tmp/aliases.yaml"

    def test_full_config_with_expected_segment_validates(self):
        """A FlexpipeConfig with viralqc.expected_segment must not raise extra="forbid"."""
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            viralqc={"expected_segment": "S"},
        )
        assert cfg.viralqc.expected_segment == "S"

    def test_unknown_viralqc_key_still_rejected(self):
        """extra="forbid" still blocks genuinely unknown keys."""
        import pydantic

        with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
            ViralqcConfig(totally_unknown_key="x")


# ---------------------------------------------------------------------------
# 5.7 — ParametersConfig.mask_sites_file
# ---------------------------------------------------------------------------


class TestParametersMaskSitesFile:
    """mask_sites_file is an optional BED path; empty string = no BED masking."""

    def test_default_is_empty_string(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
        )
        assert cfg.parameters.mask_sites_file == ""

    def test_can_be_set_to_a_path(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            parameters={"mask_sites_file": "/some/mask.bed"},
        )
        assert cfg.parameters.mask_sites_file == "/some/mask.bed"


class TestExternalizedFollowupConfig:
    """Configuration hooks for flexible follow-up registries and shared caches."""

    def test_date_formats_and_shared_cache_are_accepted(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            curation={"date_formats": "/tmp/date_formats.yaml"},
            coordinates={"shared_cache": "/tmp/cache_coordinates.tsv"},
        )
        assert cfg.curation.date_formats == "/tmp/date_formats.yaml"
        assert cfg.coordinates.shared_cache == "/tmp/cache_coordinates.tsv"


# ---------------------------------------------------------------------------
# 5.1 — QcConfig.min_sequences
# ---------------------------------------------------------------------------


class TestQcMinSequences:
    """min_sequences default and custom values."""

    def test_default_is_10(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
        )
        assert cfg.qc.min_sequences == 10

    def test_can_be_set_to_zero_to_disable(self):
        cfg = FlexpipeConfig(
            data_source="pathoplexus",
            pathoplexus={"organism": "yellow-fever"},
            qc={
                "min_sequences": 0,
                "genome_quality": ["A", "B"],
                "min_coverage": 0.70,
                "required_columns": ["strain", "date", "clade"],
            },
        )
        assert cfg.qc.min_sequences == 0


# ---------------------------------------------------------------------------
# FragmentConfig + mode='fragment' cross-field validators
# ---------------------------------------------------------------------------


class TestFragmentConfig:
    """Tests for mode='fragment' configuration."""

    def _base(self, **overrides):
        kwargs = dict(
            data_source="pathoplexus",
            pathoplexus={"organism": "measles"},
            viralqc={"mode": "run", "expected_virus": "measles"},
        )
        kwargs.update(overrides)
        return kwargs

    # ── defaults ─────────────────────────────────────────────────────────────

    def test_whole_genome_is_default_mode(self):
        cfg = FlexpipeConfig(**self._base())
        assert cfg.mode == "whole-genome"

    def test_fragment_defaults(self):
        cfg = FlexpipeConfig(**self._base())
        assert cfg.fragment.target_gene == ""
        assert cfg.fragment.min_target_coverage == pytest.approx(0.70)
        assert cfg.fragment.target_quality == ["A", "B"]

    # ── valid fragment configs ────────────────────────────────────────────────

    def test_fragment_mode_valid(self):
        cfg = FlexpipeConfig(
            **self._base(
                mode="fragment",
                fragment={"target_gene": "N", "min_target_coverage": 0.70},
            )
        )
        assert cfg.mode == "fragment"
        assert cfg.fragment.target_gene == "N"

    def test_fragment_min_target_coverage_bounds(self):
        """0.0 and 1.0 are valid; <0 and >1 are not."""
        for valid in (0.0, 0.5, 1.0):
            cfg = FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N", "min_target_coverage": valid},
                )
            )
            assert cfg.fragment.min_target_coverage == pytest.approx(valid)

        with pytest.raises(pydantic.ValidationError):
            FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N", "min_target_coverage": -0.01},
                )
            )
        with pytest.raises(pydantic.ValidationError):
            FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N", "min_target_coverage": 1.01},
                )
            )

    # ── cross-field validators ────────────────────────────────────────────────

    def test_fragment_mode_missing_target_gene_raises(self):
        with pytest.raises(pydantic.ValidationError, match="fragment.target_gene is required"):
            FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": ""},
                )
            )

    def test_fragment_mode_no_fragment_section_raises(self):
        """Omitting the fragment section defaults target_gene to '' → error."""
        with pytest.raises(pydantic.ValidationError, match="fragment.target_gene is required"):
            FlexpipeConfig(**self._base(mode="fragment"))

    def test_fragment_mode_skip_viralqc_raises(self):
        with pytest.raises(pydantic.ValidationError, match="incompatible with viralqc.mode='skip'"):
            FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N"},
                    viralqc={"mode": "skip"},
                )
            )

    def test_fragment_mode_precomputed_viralqc_raises(self):
        with pytest.raises(
            pydantic.ValidationError,
            match="not yet supported",
        ):
            FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N"},
                    viralqc={
                        "mode": "precomputed",
                        "precomputed": "/tmp/fake_results.tsv",
                    },
                )
            )

    def test_invalid_mode_raises(self):
        with pytest.raises(pydantic.ValidationError):
            FlexpipeConfig(**self._base(mode="gene"))  # unknown mode

    def test_whole_genome_with_fragment_section_is_fine(self):
        """A fragment: section in a whole-genome build is silently ignored."""
        cfg = FlexpipeConfig(
            **self._base(
                mode="whole-genome",
                fragment={"target_gene": "N"},
            )
        )
        assert cfg.mode == "whole-genome"
        assert cfg.fragment.target_gene == "N"

    # ── target_quality validator ──────────────────────────────────────────────

    def test_target_quality_valid_grades(self):
        """A, B, C, D are all accepted individually or combined."""
        for grades in (["A"], ["B"], ["A", "B"], ["A", "B", "C", "D"]):
            cfg = FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N", "target_quality": grades},
                )
            )
            assert sorted(cfg.fragment.target_quality) == sorted(grades)

    def test_target_quality_empty_list_raises(self):
        """An empty target_quality silently excludes all sequences — reject it."""
        with pytest.raises(pydantic.ValidationError, match="must not be empty"):
            FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N", "target_quality": []},
                )
            )

    def test_target_quality_invalid_grade_raises(self):
        """Grade 'Z' is not a valid ViralQC quality level."""
        with pytest.raises(pydantic.ValidationError, match="invalid grades"):
            FlexpipeConfig(
                **self._base(
                    mode="fragment",
                    fragment={"target_gene": "N", "target_quality": ["A", "Z"]},
                )
            )

    def test_target_quality_grades_uppercased(self):
        """Validator normalises lowercase grades to uppercase."""
        cfg = FlexpipeConfig(
            **self._base(
                mode="fragment",
                fragment={"target_gene": "N", "target_quality": ["a", "b"]},
            )
        )
        assert set(cfg.fragment.target_quality) == {"A", "B"}
