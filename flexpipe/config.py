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

import logging
import os
from pathlib import Path
from typing import List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section models
# ---------------------------------------------------------------------------

class FilesConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    keep:           str = "config/keep.txt"
    ignore:         str = "config/ignore.txt"
    cache:          str = "config/cache_coordinates.tsv"
    reference:      str = "config/reference.gb"
    clades:         str = "config/clades.tsv"
    auspice_config: str = "config/auspice_config.json"


class ParametersConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    mask_5prime:         int   = 0
    mask_3prime:         int   = 0
    mask_sites:          str   = ""
    ufboot:              int   = 1000
    model:               str   = "MFP"
    root:                str   = "least-squares"
    coalescent:          str   = "skyline"
    date_inference:      str   = "marginal"
    divergence_units:    str   = "mutations"
    clock_filter_iqd:    int   = 4
    ancestral_inference: str   = "joint"


class OptionsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    threads: int = 4


class CoordinatesConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    columns: str = "country"  # space-separated list of columns to geocode


class ColoursHueTablesConfig(BaseModel):
    """Optional override paths for bundled *_hues.tsv files."""
    model_config = ConfigDict(extra="allow")
    region:   Optional[str] = None
    host:     Optional[str] = None
    source:   Optional[str] = None
    data_use: Optional[str] = None


class ColoursConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    clade:      str = "clade_truncated clade"
    geo:        str = "region division location"
    source:     str = "source"
    data_use:   str = "data_use"
    hue_tables: ColoursHueTablesConfig = Field(default_factory=ColoursHueTablesConfig)


class TraitsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    columns: str = "division location clade"


class SubsamplingConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    random_seed: int = 42


class CurationConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    clade_levels:    int           = 1
    clade_separator: str           = "."
    host_rules:      Optional[str] = None  # override path for host_rules.yaml


class RegionsConfig(BaseModel):
    """Override paths for bundled region-mapping TSV files."""
    model_config = ConfigDict(extra="allow")
    country_map:            Optional[str] = None
    division_map:           Optional[str] = None
    division_abbreviations: Optional[str] = None
    division_parser:        str           = "brazil"  # "brazil" | "none"


class PathoplexusConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    organism:             str   = ""
    base_url:             str   = "https://lapis.pathoplexus.org"
    metadata_endpoint:    str   = "details"
    sequences_endpoint:   str   = "unalignedNucleotideSequences"
    min_completeness:     float = 0.70


class NcbiConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    taxid:       int   = 0
    genome_size: int   = 0
    min_length:  float = 0.7
    max_length:  float = 1.1
    email:       str   = ""
    api_key:     str   = ""


class ViralqcConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    conda_env:               str = "viralQC"
    clade_column:            str = "clade"
    datasets_dir:            str = ""
    blast_database:          str = ""
    blast_database_metadata: str = ""


class QcConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    genome_quality:    List[str] = ["A", "B"]
    min_coverage:      float     = 0.70
    required_columns:  List[str] = Field(
        default_factory=lambda: ["strain", "date", "clade"]
    )


class LocalSequencesConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled:   bool = False
    metadata:  str  = "data/metadata.xlsx"
    sequences: str  = "data/new_sequences.fasta"


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
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

    files:           FilesConfig           = Field(default_factory=FilesConfig)
    parameters:      ParametersConfig      = Field(default_factory=ParametersConfig)
    options:         OptionsConfig         = Field(default_factory=OptionsConfig)
    coordinates:     CoordinatesConfig     = Field(default_factory=CoordinatesConfig)
    colours:         ColoursConfig         = Field(default_factory=ColoursConfig)
    traits:          TraitsConfig          = Field(default_factory=TraitsConfig)
    subsampling:     SubsamplingConfig     = Field(default_factory=SubsamplingConfig)
    curation:        CurationConfig        = Field(default_factory=CurationConfig)
    regions:         RegionsConfig         = Field(default_factory=RegionsConfig)
    region_source:   Literal["country", "division"] = "country"
    data_source:     Literal["pathoplexus", "ncbi"]  = "pathoplexus"
    pathoplexus:     PathoplexusConfig     = Field(default_factory=PathoplexusConfig)
    ncbi:            NcbiConfig            = Field(default_factory=NcbiConfig)
    viralqc:         ViralqcConfig         = Field(default_factory=ViralqcConfig)
    qc:              QcConfig              = Field(default_factory=QcConfig)
    local_sequences: LocalSequencesConfig  = Field(default_factory=LocalSequencesConfig)
    paths:           PathsConfig           = Field(default_factory=PathsConfig)

    @model_validator(mode="after")
    def check_pathoplexus_config(self) -> "FlexpipeConfig":
        if self.data_source == "pathoplexus" and not self.pathoplexus.organism:
            raise ValueError(
                "pathoplexus.organism is required when data_source='pathoplexus'.\n"
                "Example: organism: 'yellow-fever'"
            )
        return self

    @model_validator(mode="after")
    def check_ncbi_config(self) -> "FlexpipeConfig":
        if self.data_source == "ncbi" and self.ncbi.taxid == 0:
            raise ValueError(
                "ncbi.taxid is required when data_source='ncbi'.\n"
                "Example: taxid: 11089  # Yellow fever virus"
            )
        return self

    @model_validator(mode="after")
    def check_region_override_paths(self) -> "FlexpipeConfig":
        """Verify any explicitly specified region-map override paths exist."""
        for attr, label in [
            ("country_map",            "regions.country_map"),
            ("division_map",           "regions.division_map"),
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
    def check_hue_table_override_paths(self) -> "FlexpipeConfig":
        """Verify any explicitly specified hue-table override paths exist."""
        for attr, label in [
            ("region",   "colours.hue_tables.region"),
            ("host",     "colours.hue_tables.host"),
            ("source",   "colours.hue_tables.source"),
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
    3. ``SystemExit`` with a clear, actionable message

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
        raise SystemExit(
            "ViralQC datasets directory not configured.\n"
            "Set 'viralqc.datasets_dir' in your config.yaml, or export the "
            "VIRALQC_DATASETS_DIR environment variable pointing to your ViralQC "
            "datasets directory (e.g. /path/to/viralQC/datasets)."
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _load_yaml(path: Union[str, Path]) -> dict:
    """Load a YAML file and return a plain dictionary."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(
    config_path: Union[str, Path],
    workdir: Optional[Union[str, Path]] = None,
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
    raw = _load_yaml(config_path)
    logger.info("Loaded config from %s", config_path)

    # Inject workdir override before validation
    if workdir is not None:
        raw.setdefault("paths", {})["workdir"] = str(workdir)

    cfg = FlexpipeConfig(**raw)

    # Resolve ViralQC paths (side-effectful — separate from pydantic validation)
    if not skip_viralqc and "viralqc" in raw:
        cfg.viralqc = resolve_viralqc_paths(cfg.viralqc)

    return cfg
