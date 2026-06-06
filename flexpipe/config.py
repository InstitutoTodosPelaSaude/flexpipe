"""
Configuration loading, validation, and resolution for flexpipe.

Provides a ``FlexpipeConfig`` pydantic model that:
- Mirrors the structure of ``config.yaml`` with typed defaults
- Resolves ViralQC dataset paths (config → env var → fail-fast preflight)
- Loads bundled default data files (region maps, host rules, hue tables)
  when the config does not specify overrides
- Performs cross-field validation (e.g. data_source is exclusive)

Usage::

    from flexpipe.config import load_config
    cfg = load_config("builds/yfv-brazil/config.yaml", workdir="/tmp/run")
    print(cfg.data_source)          # "pathoplexus"
    print(cfg.paths.workdir)        # "/tmp/run"
"""

from __future__ import annotations

import copy
import logging
import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_COLUMN_LIST_RE = re.compile(r"^[A-Za-z0-9_ .-]+$")


def _validate_column_list(value: str, label: str) -> str:
    """Validate a space-separated column list used in shell-rendered commands."""
    if not value or not str(value).strip():
        raise ValueError(f"{label} must be a non-empty column list")
    if not _COLUMN_LIST_RE.match(str(value)):
        raise ValueError(
            f"{label} contains unsupported characters. "
            "Only letters, numbers, spaces, underscores, dots, and hyphens are allowed."
        )
    return value


def _is_empty_path(value) -> bool:
    return value is None or str(value).strip() == ""


def _resolve_path_value(
    value,
    *,
    build_dir: Path,
    repo_root: Path = _REPO_ROOT,
    must_exist: bool = False,
    label: str = "path",
):
    """Resolve a config path relative to the build dir, with repo-root compatibility fallback."""
    if _is_empty_path(value):
        return value
    p = Path(str(value)).expanduser()
    if p.is_absolute():
        resolved = p.resolve(strict=False)
    else:
        build_candidate = (build_dir / p).resolve(strict=False)
        repo_candidate = (repo_root / p).resolve(strict=False)
        if build_candidate.exists():
            resolved = build_candidate
        elif repo_candidate.exists():
            # Backwards compatibility for current configs that spell paths as
            # builds/<name>/file rather than file relative to config.yaml.
            resolved = repo_candidate
        else:
            resolved = build_candidate
    if must_exist and not resolved.exists():
        raise ValueError(f"{label} path not found: {resolved}")
    return str(resolved)


def _resolve_section_paths(
    raw: dict,
    section: str,
    keys: list[str],
    *,
    build_dir: Path,
    must_exist: bool = False,
) -> None:
    data = raw.get(section)
    if not isinstance(data, dict):
        return
    for key in keys:
        if key in data and not _is_empty_path(data[key]):
            data[key] = _resolve_path_value(
                data[key],
                build_dir=build_dir,
                must_exist=must_exist,
                label=f"{section}.{key}",
            )


def resolve_config_paths(raw: dict, config_path: str | Path) -> dict:
    """Return a deep copy of raw config with path-like values made absolute.

    Relative paths are resolved relative to the build config directory.  For
    compatibility with existing build configs that use repo-root-relative paths
    such as ``builds/yfv-brazil/reference.gb``, an existing repo-root candidate
    is preferred when the build-dir candidate does not exist.
    """
    out = copy.deepcopy(raw)
    build_dir = Path(config_path).resolve().parent

    _resolve_section_paths(
        out,
        "files",
        ["keep", "ignore", "reference", "clades", "auspice_config", "subsample_config"],
        build_dir=build_dir,
        must_exist=True,
    )
    _resolve_section_paths(out, "files", ["cache"], build_dir=build_dir)
    _resolve_section_paths(out, "local_sequences", ["metadata", "sequences"], build_dir=build_dir)
    _resolve_section_paths(
        out, "parameters", ["mask_sites_file"], build_dir=build_dir, must_exist=True
    )
    _resolve_section_paths(out, "coordinates", ["force_file"], build_dir=build_dir, must_exist=True)
    _resolve_section_paths(
        out,
        "regions",
        ["country_map", "division_map", "division_abbreviations"],
        build_dir=build_dir,
        must_exist=True,
    )
    _resolve_section_paths(out, "curation", ["host_rules"], build_dir=build_dir, must_exist=True)

    hue_tables = out.get("colours", {}).get("hue_tables")
    if isinstance(hue_tables, dict):
        for key in ["region", "host", "source", "data_use"]:
            if key in hue_tables and not _is_empty_path(hue_tables[key]):
                hue_tables[key] = _resolve_path_value(
                    hue_tables[key],
                    build_dir=build_dir,
                    must_exist=True,
                    label=f"colours.hue_tables.{key}",
                )

    local = out.get("local_sequences", {})
    if isinstance(local, dict) and local.get("enabled"):
        for key in ["metadata", "sequences"]:
            path = local.get(key, "")
            if _is_empty_path(path) or not Path(path).exists():
                raise ValueError(
                    f"local_sequences.enabled=true but local_sequences.{key} was not found: {path}"
                )

    return out


def _resolve_subsample_path_value(value, *, base_dir: Path, repo_root: Path = _REPO_ROOT):
    if isinstance(value, list):
        return [
            _resolve_subsample_path_value(item, base_dir=base_dir, repo_root=repo_root)
            for item in value
        ]
    if _is_empty_path(value):
        return value
    return _resolve_path_value(value, build_dir=base_dir, repo_root=repo_root)


def resolve_subsample_paths(raw: dict, subsample_config_path: str | Path) -> dict:
    """Resolve include/exclude paths inside an augur subsample config."""
    out = copy.deepcopy(raw)
    base_dir = Path(subsample_config_path).resolve().parent
    defaults = out.get("defaults")
    if isinstance(defaults, dict) and "exclude" in defaults:
        defaults["exclude"] = _resolve_subsample_path_value(defaults["exclude"], base_dir=base_dir)

    samples = out.get("samples")
    if isinstance(samples, dict):
        for sample in samples.values():
            if not isinstance(sample, dict):
                continue
            for key in ["include", "exclude"]:
                if key in sample:
                    sample[key] = _resolve_subsample_path_value(sample[key], base_dir=base_dir)
    return out


# ---------------------------------------------------------------------------
# Section models
# ---------------------------------------------------------------------------


class FilesConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    keep: str = "config/keep.txt"
    ignore: str = "config/ignore.txt"
    cache: str = "config/cache_coordinates.tsv"
    reference: str = "config/reference.gb"
    clades: str = "config/clades.tsv"
    auspice_config: str = "config/auspice_config.json"
    subsample_config: str = "config/subsample.yaml"


class ParametersConfig(BaseModel):
    model_config = ConfigDict(extra="allow")  # allow augur-specific extensions
    mask_5prime: int = Field(default=0, ge=0)
    mask_3prime: int = Field(default=0, ge=0)
    mask_sites: str = ""
    mask_sites_file: str = (
        ""  # optional BED file of problematic sites; positional values are per-reference
    )
    ufboot: int = Field(default=1000, ge=0)
    model: str = Field(default="MFP", min_length=1)
    root: Literal["least-squares", "min_dev", "oldest", "best"] = "least-squares"
    coalescent: Literal["skyline", "opt", "const", "fixed"] = "skyline"
    date_inference: Literal["marginal", "joint"] = "marginal"
    divergence_units: Literal["mutations", "mutations-per-site"] = "mutations"
    clock_filter_iqd: int = Field(default=4, ge=0)
    ancestral_inference: Literal["joint", "marginal"] = "joint"


class OptionsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threads: int = Field(default=4, ge=1)


class CoordinatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: str = "country"
    force_file: str | None = None

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: str) -> str:
        return _validate_column_list(value, "coordinates.columns")


class ColoursHueTablesConfig(BaseModel):
    """Optional override paths for bundled *_hues.tsv files."""

    model_config = ConfigDict(extra="forbid")
    region: str | None = None
    host: str | None = None
    source: str | None = None
    data_use: str | None = None


class ColoursConfig(BaseModel):
    model_config = ConfigDict(extra="allow")  # allow per-build color category extensions
    clade: str = "clade_truncated clade"
    geo: str = "region division location"
    source: str = "source"
    data_use: str = "data_use"
    hue_tables: ColoursHueTablesConfig = Field(default_factory=ColoursHueTablesConfig)

    @field_validator("clade", "geo", "source", "data_use")
    @classmethod
    def validate_colour_levels(cls, value: str) -> str:
        return _validate_column_list(value, "colours")


class TraitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: str = "division location clade"

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: str) -> str:
        return _validate_column_list(value, "traits.columns")


class SubsamplingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    random_seed: int = 42


class CurationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clade_levels: int = 1
    clade_separator: str = "."
    host_rules: str | None = None


class RegionsConfig(BaseModel):
    """Override paths for bundled region-mapping TSV files."""

    model_config = ConfigDict(extra="forbid")
    country_map: str | None = None
    division_map: str | None = None
    division_abbreviations: str | None = None
    division_parser: str = "brazil"


class PathoplexusConfig(BaseModel):
    model_config = ConfigDict(extra="allow")  # allow LAPIS-specific query params
    organism: str = ""
    base_url: str = "https://lapis.pathoplexus.org"
    metadata_endpoint: str = "details"
    sequences_endpoint: str = "unalignedNucleotideSequences"
    min_completeness: float = 0.70


class NcbiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taxid: int = 0
    genome_size: int = 0
    min_length: float = 0.7
    max_length: float = 1.1
    email: str = ""
    api_key: str = ""
    min_date: str = ""
    extra_search_term: str = ""


class ViralqcConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conda_env: str = "viralQC"
    clade_column: str = "clade"
    datasets_dir: str = ""
    blast_database: str = ""
    blast_database_metadata: str = ""
    expected_virus: str | None = None
    expected_segment: str = ""  # single expected segment (e.g. "L", "S"); flags wrong-segment reads
    runner: Literal["conda", "mamba", "micromamba", "direct"] = "conda"
    executable: str = "vqc"


class QcConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    genome_quality: list[str] = ["A", "B"]
    min_coverage: float = Field(default=0.70, ge=0.0, le=1.0)
    required_columns: list[str] = Field(default_factory=lambda: ["strain", "date", "clade"])
    min_sequences: int = Field(
        default=10, ge=0
    )  # minimum subsampled sequences required before phylogenetics


class LocalSequencesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    metadata: str = "data/metadata.xlsx"
    sequences: str = "data/new_sequences.fasta"


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workdir: str = "workdir"


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class FlexpipeConfig(BaseModel):
    """Root configuration model for a flexpipe build.

    All sections have sensible defaults so a minimal config.yaml reproduces
    the YFV-Brazil example build.  Override keys are additive — omitting a
    section falls back to the bundled default data files.
    """

    model_config = ConfigDict(extra="allow")

    files: FilesConfig = Field(default_factory=FilesConfig)
    parameters: ParametersConfig = Field(default_factory=ParametersConfig)
    options: OptionsConfig = Field(default_factory=OptionsConfig)
    coordinates: CoordinatesConfig = Field(default_factory=CoordinatesConfig)
    colours: ColoursConfig = Field(default_factory=ColoursConfig)
    traits: TraitsConfig = Field(default_factory=TraitsConfig)
    subsampling: SubsamplingConfig = Field(default_factory=SubsamplingConfig)
    curation: CurationConfig = Field(default_factory=CurationConfig)
    regions: RegionsConfig = Field(default_factory=RegionsConfig)
    region_source: Literal["country", "division"] = "country"
    data_source: Literal["pathoplexus", "ncbi"] = "pathoplexus"
    pathoplexus: PathoplexusConfig = Field(default_factory=PathoplexusConfig)
    ncbi: NcbiConfig = Field(default_factory=NcbiConfig)
    viralqc: ViralqcConfig = Field(default_factory=ViralqcConfig)
    qc: QcConfig = Field(default_factory=QcConfig)
    local_sequences: LocalSequencesConfig = Field(default_factory=LocalSequencesConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    @model_validator(mode="after")
    def check_pathoplexus_config(self) -> FlexpipeConfig:
        if self.data_source == "pathoplexus" and not self.pathoplexus.organism:
            raise ValueError(
                "pathoplexus.organism is required when data_source='pathoplexus'.\n"
                "Example: organism: 'yellow-fever'"
            )
        return self

    @model_validator(mode="after")
    def check_ncbi_config(self) -> FlexpipeConfig:
        if self.data_source == "ncbi" and self.ncbi.taxid == 0:
            raise ValueError(
                "ncbi.taxid is required when data_source='ncbi'.\n"
                "Example: taxid: 11089  # Yellow fever virus"
            )
        if self.data_source == "ncbi" and not (self.ncbi.email or os.environ.get("NCBI_EMAIL")):
            raise ValueError(
                "ncbi.email or NCBI_EMAIL is required when data_source='ncbi'.\n"
                "NCBI Entrez requires a real contact email for automated clients."
            )
        return self

    @model_validator(mode="after")
    def check_region_override_paths(self) -> FlexpipeConfig:
        """Verify any explicitly specified region-map override paths exist."""
        for attr, label in [
            ("country_map", "regions.country_map"),
            ("division_map", "regions.division_map"),
            ("division_abbreviations", "regions.division_abbreviations"),
        ]:
            path = getattr(self.regions, attr)
            if path and not Path(path).exists():
                raise ValueError(
                    f"{label} override path not found: {path}\n"
                    "Remove the key to use the bundled default."
                )
        return self

    @model_validator(mode="after")
    def check_hue_table_override_paths(self) -> FlexpipeConfig:
        """Verify any explicitly specified hue-table override paths exist."""
        for attr, label in [
            ("region", "colours.hue_tables.region"),
            ("host", "colours.hue_tables.host"),
            ("source", "colours.hue_tables.source"),
            ("data_use", "colours.hue_tables.data_use"),
        ]:
            path = getattr(self.colours.hue_tables, attr)
            if path and not Path(path).exists():
                raise ValueError(
                    f"{label} override path not found: {path}\n"
                    "Remove the key to use the bundled default."
                )
        return self


# ---------------------------------------------------------------------------
# ViralQC path resolution
# ---------------------------------------------------------------------------


def resolve_viralqc_paths(viralqc_cfg: ViralqcConfig) -> ViralqcConfig:
    """Resolve and validate ViralQC dataset paths.

    Resolution order for ``datasets_dir``:
    1. ``viralqc.datasets_dir`` from config (if non-empty, not a ``/home/`` placeholder)
    2. ``$VIRALQC_DATASETS_DIR`` environment variable
    3. Submodule default: ``<repo-root>/viralQC/datasets`` (auto-discovered when the
       viralQC git submodule is present and ``scripts/install_viralqc.sh`` has been run)
    4. ``SystemExit`` with a clear, actionable message

    ``blast_database`` and ``blast_database_metadata`` default to
    ``<datasets_dir>/blast.fasta`` and ``<datasets_dir>/blast.tsv`` unless
    explicitly overridden.

    Args:
        viralqc_cfg: The validated ``ViralqcConfig`` model.

    Returns:
        Updated ``ViralqcConfig`` with resolved, validated paths.

    Raises:
        SystemExit: If the datasets directory cannot be resolved or does not exist.
    """
    data = viralqc_cfg.model_dump()

    # Resolve datasets_dir
    datasets_dir = data.get("datasets_dir", "")
    if not datasets_dir or str(datasets_dir).startswith("/home/"):
        datasets_dir = os.environ.get("VIRALQC_DATASETS_DIR", "")
    if not datasets_dir:
        # Fallback: auto-discover the viralQC submodule bundled with the repo.
        # Path(__file__) is <repo>/flexpipe/config.py → parents[1] is <repo>.
        _submodule_datasets = Path(__file__).resolve().parents[1] / "viralQC" / "datasets"
        if _submodule_datasets.exists():
            datasets_dir = str(_submodule_datasets)
            logger.debug("ViralQC datasets resolved from submodule: %s", datasets_dir)
    if not datasets_dir:
        raise SystemExit(
            "ViralQC datasets directory not configured.\n"
            "Options (in order of precedence):\n"
            "  1. Set 'viralqc.datasets_dir' in your config.yaml\n"
            "  2. Export VIRALQC_DATASETS_DIR=/path/to/viralQC/datasets\n"
            "  3. Run 'bash scripts/install_viralqc.sh' to set up the bundled submodule\n"
            "See: https://github.com/InstitutoTodosPelaSaude/viralQC"
        )
    datasets_dir = Path(datasets_dir)
    if not datasets_dir.exists():
        raise SystemExit(
            f"ViralQC datasets directory not found: {datasets_dir}\n"
            "Ensure ViralQC is installed and the path is correct.\n"
            "See: https://github.com/InstitutoTodosPelaSaude/viralQC"
        )
    data["datasets_dir"] = str(datasets_dir)

    # Derive blast paths from datasets_dir unless already explicitly set
    blast_db = data.get("blast_database", "")
    if not blast_db or str(blast_db).startswith("/home/"):
        data["blast_database"] = str(datasets_dir / "blast.fasta")
    blast_meta = data.get("blast_database_metadata", "")
    if not blast_meta or str(blast_meta).startswith("/home/"):
        data["blast_database_metadata"] = str(datasets_dir / "blast.tsv")

    # Preflight: verify blast database exists
    blast_path = Path(data["blast_database"])
    if not blast_path.exists():
        raise SystemExit(
            f"ViralQC BLAST database not found: {blast_path}\n"
            f"Expected under datasets_dir: {datasets_dir}\n"
            "Check your ViralQC installation."
        )
    logger.debug("ViralQC paths resolved: datasets_dir=%s", datasets_dir)
    return ViralqcConfig(**data)


def resolve_subsample_config(
    raw: dict,
    run_date: str | None,
    subsample_config_path: str | Path | None = None,
) -> dict:
    """Return a copy of the subsample config dict with ``defaults.max_date`` injected.

    When *run_date* is provided, it is written into the ``defaults`` section of the
    subsample config as the ``max_date`` upper bound for ``augur subsample``.  This
    ensures a scheduled rerun with ``--run-date 2026-01-01`` is bounded by that date
    rather than anchored to the system clock.

    When *run_date* is empty or ``None`` the dict is returned unchanged — preserving
    current behaviour for direct ``snakemake`` invocations that do not pass
    ``--config run_date=``.

    Args:
        raw: Parsed subsample config dict (e.g. from ``builds/<name>/subsample.yaml``).
        run_date: Reference date in ``YYYY-MM-DD`` format, or ``None`` / ``""`` to skip.

    Returns:
        A shallow copy of *raw* with the ``defaults`` section updated.
    """
    out = (
        resolve_subsample_paths(raw, subsample_config_path)
        if subsample_config_path is not None
        else copy.deepcopy(raw)
    )
    if not run_date:
        return out
    out.setdefault("defaults", {})["max_date"] = run_date
    logger.debug("resolve_subsample_config: set defaults.max_date=%s", run_date)
    return out


def _deep_update(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* and return *base*."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def write_snakemake_config_overrides(
    cfg: FlexpipeConfig, path: str | Path, config_path: str | Path
) -> Path:
    """Write a complete resolved config YAML for Snakemake to consume as its sole --configfile.

    Snakemake 9+ loads only the last ``--configfile`` when multiple are supplied, so all
    config values must live in one file.  This function loads the raw build ``config.yaml``
    (preserving every field the Snakefiles expect), then overrides the ``viralqc`` section
    with pydantic-resolved paths (auto-discovered dataset dirs, etc.).

    Args:
        cfg: Validated ``FlexpipeConfig`` with resolved ViralQC paths.
        path: Output YAML path (parent directories are created if needed).
        config_path: Path to the original build ``config.yaml`` (used to load all fields
            that the Snakefiles read but that ``FlexpipeConfig`` may not explicitly model).

    Returns:
        The path written.
    """
    # Start from pydantic defaults so omitted sections are still present, then
    # overlay the real build YAML so build-specific file paths/parameters win.
    # Runtime-resolved sections are written last.
    raw = cfg.model_dump()
    build_raw = resolve_config_paths(_load_yaml(config_path), config_path)
    _deep_update(raw, build_raw)
    raw["viralqc"] = cfg.viralqc.model_dump()
    raw["paths"] = cfg.paths.model_dump()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, default_flow_style=False, sort_keys=False)
    logger.debug("Wrote resolved Snakemake config to %s", out)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _load_yaml(path: str | Path) -> dict:
    """Load a YAML file and return a plain dictionary."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(
    config_path: str | Path,
    workdir: str | Path | None = None,
    skip_viralqc: bool = False,
) -> FlexpipeConfig:
    """Load and validate a flexpipe config.yaml.

    Steps:
    1. Load the raw YAML
    2. Apply ``workdir`` override into ``paths.workdir``
    3. Validate with ``FlexpipeConfig`` (raises ``pydantic.ValidationError`` on error)
    4. Resolve ViralQC paths (raises ``SystemExit`` if not configured)

    Args:
        config_path: Path to the build's ``config.yaml``.
        workdir: Override workdir; takes precedence over ``paths.workdir`` in config.
        skip_viralqc: If ``True``, skip ViralQC path resolution (for testing / dry-run).

    Returns:
        Validated ``FlexpipeConfig`` instance.
    """
    config_path = Path(config_path).resolve()
    raw = _load_yaml(config_path)
    logger.info("Loaded config from %s", config_path)

    # Inject workdir override before validation
    if workdir is not None:
        raw.setdefault("paths", {})["workdir"] = str(workdir)

    try:
        raw = resolve_config_paths(raw, config_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    cfg = FlexpipeConfig(**raw)

    # Resolve ViralQC paths (side-effectful — separate from pydantic validation)
    if not skip_viralqc and "viralqc" in raw:
        cfg.viralqc = resolve_viralqc_paths(cfg.viralqc)

    return cfg
