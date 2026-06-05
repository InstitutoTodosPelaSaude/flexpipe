"""
Shared pytest fixtures for flexpipe tests.

Provides:
- ``tmp_workdir``: a temporary WorkdirPaths instance backed by a tmp_path
- ``sample_config``: a minimal but valid config dict (YFV-Brazil like)
- ``sample_metadata_df``: a small DataFrame representing curated metadata
"""

from pathlib import Path

import pandas as pd
import pytest

from flexpipe.paths import WorkdirPaths


@pytest.fixture()
def tmp_workdir(tmp_path: Path) -> WorkdirPaths:
    """Return a WorkdirPaths pointing at a fresh temp directory."""
    paths = WorkdirPaths.from_root(tmp_path / "workdir")
    paths.ensure_dirs()
    return paths


@pytest.fixture()
def sample_config(tmp_path: Path) -> dict:
    """Return a minimal resolved config dict (no ViralQC paths to avoid preflight)."""
    return {
        "data_source": "pathoplexus",
        "region_source": "division",
        "pathoplexus": {
            "organism": "yellow-fever",
            "base_url": "https://lapis.pathoplexus.org",
            "metadata_endpoint": "details",
            "sequences_endpoint": "unalignedNucleotideSequences",
            "min_completeness": 0.70,
        },
        "curation": {
            "clade_levels": 1,
            "clade_separator": ".",
        },
        "colours": {
            "clade": "clade_truncated clade",
            "geo": "region division location",
            "source": "source",
            "data_use": "data_use",
        },
        "qc": {
            "genome_quality": ["A", "B"],
            "min_coverage": 0.70,
            "required_columns": ["strain", "date", "division", "clade"],
        },
        "paths": {"workdir": str(tmp_path / "workdir")},
    }


@pytest.fixture()
def sample_metadata_df() -> pd.DataFrame:
    """Return a small curated metadata DataFrame with diverse test cases."""
    rows = [
        # Brazil compound-division formats
        {
            "strain": "SEQ001",
            "date": "2023-01-15",
            "country": "Brazil",
            "division": "Espírito Santo, Domingos Martins",
            "location": "",
            "clade": "I",
            "genome_quality": "A",
            "coverage": "0.95",
            "source": "Pathoplexus",
            "data_use": "OPEN",
            "host": "human",
        },
        {
            "strain": "SEQ002",
            "date": "2022-06-20",
            "country": "Brazil",
            "division": "ES, Serra [IBGE7 3205002]",
            "location": "",
            "clade": "I",
            "genome_quality": "B",
            "coverage": "0.85",
            "source": "Pathoplexus",
            "data_use": "OPEN",
            "host": "Alouatta palliata",
        },
        {
            "strain": "SEQ003",
            "date": "2021-03-10",
            "country": "Brazil",
            "division": "Nova Lima, Minas Gerais",
            "location": "Nova Lima",
            "clade": "II",
            "genome_quality": "A",
            "coverage": "0.92",
            "source": "ITpS",
            "data_use": "OPEN",
            "host": "Homo sapiens",
        },
        # Non-Brazil (continent mapping path)
        {
            "strain": "SEQ004",
            "date": "2020-11-05",
            "country": "Colombia",
            "division": "Antioquia",
            "location": "Medellín",
            "clade": "III",
            "genome_quality": "A",
            "coverage": "0.88",
            "source": "NCBI",
            "data_use": "OPEN",
            "host": "human",
        },
        # Quality grades C and D (should be filtered out downstream)
        {
            "strain": "SEQ005",
            "date": "2023-07-01",
            "country": "Brazil",
            "division": "São Paulo",
            "location": "",
            "clade": "I",
            "genome_quality": "C",
            "coverage": "0.50",
            "source": "Pathoplexus",
            "data_use": "OPEN",
            "host": "human",
        },
        {
            "strain": "SEQ006",
            "date": "2023-07-02",
            "country": "Brazil",
            "division": "Rio de Janeiro",
            "location": "",
            "clade": "",
            "genome_quality": "D",
            "coverage": "0.30",
            "source": "Pathoplexus",
            "data_use": "OPEN",
            "host": "human",
        },
    ]
    return pd.DataFrame(rows)
