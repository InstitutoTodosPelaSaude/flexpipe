"""Unit tests for alias-backed ViralQC virus and segment matching."""

import pandas as pd

from flexpipe.curate.viralqc_aliases import (
    labels_match_expected,
    normalize_label,
    resolve_expected_entry,
)
from flexpipe.curate.viralqc_join import join_viralqc


def _metadata(*strains):
    return pd.DataFrame({"strain": list(strains), "date": ["2026-01-01"] * len(strains)})


def _write_viralqc(tmp_path, rows):
    path = tmp_path / "results.tsv"
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)
    return path


def test_normalize_label_ignores_case_spacing_and_punctuation():
    assert normalize_label("Influenza A virus (H1N1)") == "influenza a virus h1n1"
    assert normalize_label("RSV-A") == normalize_label("rsv a")


def test_resolves_alias_key_and_literal_fallback():
    assert resolve_expected_entry("rsv_a", "viruses").key == "rsv_a"
    # "Yellow fever virus" is now a registered alias for the yfv key
    assert resolve_expected_entry("Yellow fever virus", "viruses").key == "yfv"
    # An unregistered label falls back to a literal-key entry
    fallback = resolve_expected_entry("Some Unknown Virus", "viruses")
    assert fallback.key == "Some Unknown Virus"


def test_rsv_a_alias_accepts_dataset_names_but_not_b():
    assert labels_match_expected("Respiratory syncytial virus A", "rsv_a", "viruses")
    assert labels_match_expected("Human respiratory syncytial virus A", "rsv_a", "viruses")
    assert not labels_match_expected("Respiratory syncytial virus B", "rsv_a", "viruses")


def test_flu_aliases_match_strain_specific_virus_and_ha_segment():
    assert labels_match_expected(
        "Influenza A virus (A/California/07/2009(H1N1))",
        "flu_a_h1n1",
        "viruses",
    )
    assert labels_match_expected(
        "Influenza A virus (A/Wisconsin/67/2005(H3N2))",
        "flu_a_h3n2",
        "viruses",
    )
    assert labels_match_expected("Influenza B virus (B/Lee/1940)", "flu_b", "viruses")
    assert labels_match_expected("HA", "ha", "segments")
    assert labels_match_expected("4", "ha", "segments")
    assert not labels_match_expected("NA", "ha", "segments")


def test_dengue_aliases_remain_backwards_compatible():
    assert labels_match_expected("Dengue virus type 3", "Dengue virus type 3", "viruses")
    assert labels_match_expected("DENV-3", "Dengue virus type 3", "viruses")
    assert not labels_match_expected("DENV-4", "Dengue virus type 3", "viruses")


def test_ictv_species_names_are_metadata_not_broad_aliases():
    entry = resolve_expected_entry("Orthoflavivirus denguei", "viruses")

    assert entry.key == "Orthoflavivirus denguei"
    assert not labels_match_expected("Dengue virus type 1", "Orthoflavivirus denguei", "viruses")


def test_join_viralqc_uses_aliases_for_virus_and_segment(tmp_path):
    df = _metadata("ok", "wrong_virus", "wrong_segment")
    results = _write_viralqc(
        tmp_path,
        [
            {
                "seqName": "ok",
                "virus": "Influenza A virus (A/California/07/2009(H1N1))",
                "segment": "HA",
                "genomeQuality": "A",
            },
            {
                "seqName": "wrong_virus",
                "virus": "Influenza A virus (A/Wisconsin/67/2005(H3N2))",
                "segment": "HA",
                "genomeQuality": "A",
            },
            {
                "seqName": "wrong_segment",
                "virus": "Influenza A virus (A/California/07/2009(H1N1))",
                "segment": "NA",
                "genomeQuality": "A",
            },
        ],
    )

    out = join_viralqc(df, results, {"expected_virus": "flu_a_h1n1", "expected_segment": "ha"})

    assert out.loc[out["strain"] == "ok", "genome_quality"].iloc[0] == "A"
    assert out.loc[out["strain"] == "wrong_virus", "qc_exclusion_reason"].iloc[0] == "wrong_virus"
    assert (
        out.loc[out["strain"] == "wrong_segment", "qc_exclusion_reason"].iloc[0] == "wrong_segment"
    )


def test_unclassified_remains_wrong_when_expected_virus_is_configured(tmp_path):
    df = _metadata("seq1")
    results = _write_viralqc(
        tmp_path,
        [{"seqName": "seq1", "virus": "unclassified", "genomeQuality": "A"}],
    )

    out = join_viralqc(df, results, {"expected_virus": "rsv_a"})

    assert out.loc[0, "genome_quality"] == "D"
    assert out.loc[0, "qc_exclusion_reason"] == "wrong_virus"
