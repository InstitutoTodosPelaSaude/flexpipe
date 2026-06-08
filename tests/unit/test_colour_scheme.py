"""Unit tests for hierarchical colour scheme generation."""

import sys

import pandas as pd

from flexpipe.colors.hues import main as name2hue_main
from flexpipe.colors.scheme import build_scheme


def test_child_colour_stable_when_new_sibling_is_added():
    levels = ["serotype", "genotype"]
    wheel = {"3": "120"}
    df1 = pd.DataFrame({"serotype": ["3", "3"], "genotype": ["3I", "3III"]})
    df2 = pd.DataFrame({"serotype": ["3", "3", "3"], "genotype": ["3I", "3II", "3III"]})

    before = build_scheme(df1, levels, wheel)
    after = build_scheme(df2, levels, wheel)

    assert before["genotype"]["3I"] == after["genotype"]["3I"]
    assert before["genotype"]["3III"] == after["genotype"]["3III"]
    assert after["genotype"]["3II"].startswith("#")


def test_different_roots_use_different_hue_families():
    df = pd.DataFrame(
        {
            "continent": ["South America", "Europe"],
            "country": ["Brazil", "France"],
        }
    )
    scheme = build_scheme(df, ["continent", "country"], {"South America": "340", "Europe": "140"})

    assert scheme["continent"]["South America"] != scheme["continent"]["Europe"]
    assert scheme["country"]["Brazil"] != scheme["country"]["France"]


def test_name2hue_uses_configured_hierarchy_roots(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text(
        "strain\tcontinent\tcountry\tserotype\tgenotype\thost\tsource\tdata_use\n"
        "seq1\tSouth America\tBrazil\t3\t3III\thuman\tPathoplexus\tOPEN\n"
    )
    config = tmp_path / "config.yaml"
    config.write_text(
        "data_source: pathoplexus\n"
        "pathoplexus:\n"
        "  organism: dengue\n"
        "colours:\n"
        "  geo: continent country\n"
        "  clade: serotype genotype\n"
    )
    output = tmp_path / "name2hue.tsv"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "flexpipe-name2hue",
            "--metadata",
            str(metadata),
            "--config",
            str(config),
            "--output",
            str(output),
        ],
    )
    name2hue_main()

    text = output.read_text()
    assert "# geo (top-level = continent)" in text
    assert "South America\t" in text
    assert "# clade (top-level = serotype)" in text
    assert "3\t" in text
