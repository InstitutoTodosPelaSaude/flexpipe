#!/usr/bin/env python3
"""
Auto-generate config/name2hue.tsv.

Colour hierarchy → colour_maker.py `--levels` mapping:
  geo      →  region  country  division  location   (top-level = region)
  lineage  →  lineage_truncated  lineage               (top-level = lineage_truncated)
  host     →  host
  source   →  source
  data_use →  data_use

Only TOP-LEVEL categories need entries here.
colour_maker derives sub-level gradients automatically.

Hue wheel (0-350, step 10 — matches colour_maker's hue_to_hex table):
  0=red  30=orange  70=yellow-green  90=green  140=teal  190=cyan
  200=blue  240=dark-blue  270=purple  290=violet  340=rose

Unknown categories:
  - Continents/source/data_use/host → emit WARNING + next free hue
  - lineage_truncated → hash-based deterministic hue (same name → same hue
    across builds, no matter how many other lineages exist)

Configuration:
  lineage truncation level is set in config.yaml → subsampling.lineage_levels
  (default 3: A.D.3.3 → A.D.3)
  For other viruses change that value, curate_qc.py does the truncation upstream.
"""

import argparse
import os
import re
import sys

import pandas as pd


# ── geo (region = top-level of geo hierarchy) ────────────────────────────────
REGION_HUES = {
    "Africa":         20,
    "Asia":           70,
    "Europe":        140,
    "Europe/Asia":   190,
    "North America": 240,
    "Oceania":       290,
    "South America": 340,
}

# ── lineage (lineage_truncated = top-level of lineage hierarchy) ──────────────
# All lineage_truncated values use deterministic hash-based hues automatically.
# Same name always → same hue across builds, regardless of how many lineages exist.
# No manual curation needed as new lineages emerge.
LINEAGE_HUES = {}   # intentionally empty — hash fallback handles everything

# ── host ──────────────────────────────────────────────────────────────────────
HOST_HUES = {
    # scientific names
    "Homo sapiens":       200,
    "Mus musculus":       280,
    "Unknown":            340,
    # common names (Pathoplexus hostNameCommon field)
    "human":              200,
    "avian":               60,
    "swine":               40,
    "ferret":             150,
    "camel":              110,
    "acinonyx jubatus":   230,
    "giant anteater":     240,
    "mouse":              280,
    "house mouse":        280,
    "house mouse; mouse": 280,
    "pangolins":           70,
    "bovine":              30,
    "cattle":              30,
    "sheep":               50,
    "goat":                50,
    "horse":               20,
    "dog":                160,
    "cat":                170,
    "cairina moschata":      60,
    "swan":                  60,
    "turkey":                60,
    "domestic turkey":       60,
    "wild turkey":           60,
    "canine":               160,
    "canis lupus familiaris": 160,
    "home sapiens":          200,
    "people":                200,
    "person":                200,
}

# ── source ────────────────────────────────────────────────────────────────────
# Azul-esverdeado para bases externas públicas, verde para produção interna.
SOURCE_HUES = {
    "ITpS":         90,   # verde — sequências de vigilância internas
    "Pathoplexus": 270,   # roxo  — banco externo Pathoplexus
    "NCBI":        200,   # azul  — GenBank/NCBI Virus
    "GenBank":     200,   # alias NCBI
    "GISAID":      160,   # teal  — GISAID
}

# ── data_use ──────────────────────────────────────────────────────────────────
# Fixo: open = azul, restricted = vermelho. Não variam.
DATA_USE_HUES = {
    "open":        200,
    "OPEN":        200,
    "restricted":    0,
    "RESTRICTED":    0,
}

# ── hues that colour_maker recognizes (multiples of 10, 0-350) ───────────────
VALID_HUES = set(range(0, 360, 10))


def _natural_key(s: str):
    """Sort key that handles mixed text/numbers: A.D.2 < A.D.10."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


def spread_hues(names: list) -> dict:
    """
    Spread N names evenly across the hue wheel (0-350, multiples of 10).

    Step = floor(360 / N) rounded down to the nearest 10, minimum 10.
      N=12 → step=30  (0, 30, 60 … 330)
      N=6  → step=60  (0, 60, 120 … 300)
      N=36 → step=10  (0, 10, 20 … 350)

    Names are sorted alphabetically + numerically (A < A.1 < A.2 < A.D < A.D.10),
    so A always maps to the lowest hue and the progression follows clade order.
    Collision-free by construction: each slot is used exactly once.
    """
    n = len(names)
    if n == 0:
        return {}
    step = max(10, (360 // n // 10) * 10)
    ordered = sorted(names, key=_natural_key)
    return {name: (i * step) % 360 for i, name in enumerate(ordered)}


def nearest_valid(hue: int) -> int:
    return round(hue / 10) * 10 % 360


def collect(df, col, fixed_hues, label, use_hash_for_unknown=False):
    """
    Return {value: hue} for all unique non-empty values in df[col].
    Unknown values: spread-hues if use_hash_for_unknown, else next-free-hue.
    """
    if col not in df.columns:
        print(f"  WARNING: column '{col}' not found — skipping {label}")
        return {}, []

    values = sorted(set(
        v for v in df[col].tolist()
        if str(v).strip() not in ("", "nan", "NA", "NaN")
    ))

    result   = {}
    warnings = []
    used     = set(fixed_hues.values())

    known   = [v for v in values if v in fixed_hues]
    unknown = [v for v in values if v not in fixed_hues]

    for v in known:
        result[v] = int(fixed_hues[v])

    if unknown:
        if use_hash_for_unknown:
            n    = len(unknown)
            step = max(10, (360 // n // 10) * 10)
            spread = spread_hues(unknown)
            result.update(spread)
            warnings.append(
                f"{label}: {n} values → spread hues (step={step}, "
                f"{n} entries, range 0–{(n-1)*step})"
            )
            for name in sorted(spread, key=lambda x: spread[x]):
                warnings.append(f"  {label}: '{name}' → {spread[name]}")
        else:
            for v in unknown:
                used_result = set(result.values())
                h = 0
                for _ in range(36):  # max 36 unique hues (0-350 step 10)
                    if h not in used and h not in used_result:
                        break
                    h = (h + 10) % 360
                result[v] = h  # reuses a hue if >36 unknowns — acceptable
                warnings.append(
                    f"{label}: '{v}' has no fixed hue → assigned {h}. "
                    f"Add to the appropriate *_HUES dict in generate_name2hue.py."
                )

    return result, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Generate name2hue.tsv from curated metadata"
    )
    parser.add_argument("--metadata", required=True,
                        help="results/curated/metadata.tsv")
    parser.add_argument("--config",   required=False, default=None)
    parser.add_argument("--output",   required=True,
                        help="config/name2hue.tsv")
    args = parser.parse_args()

    print(f"Loading metadata: {args.metadata}")
    df = pd.read_csv(args.metadata, sep="\t", dtype=str).fillna("")

    all_warnings = []
    sections     = []   # (comment, {cat: hue})

    def run(comment, col, fixed, label, use_hash=False):
        result, warns = collect(df, col, fixed, label, use_hash)
        sections.append((comment, result))
        all_warnings.extend(warns)

    run("# geo (top-level = region)",
        "region",           REGION_HUES,     "region")

    run("# clade (top-level = clade_truncated) — unknown = hash-based",
        "clade_truncated", LINEAGE_HUES, "clade_truncated",
        use_hash=True)

    run("# host",
        "host",             HOST_HUES,       "host")

    run("# source",
        "source",           SOURCE_HUES,     "source")

    run("# data_use",
        "data_use",         DATA_USE_HUES,   "data_use")

    # ── write ─────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    total = 0
    with open(args.output, "w") as fh:
        fh.write("category\thue\n")
        for comment, entries in sections:
            fh.write(f"\n{comment}\n")
            for cat, hue in sorted(entries.items()):
                fh.write(f"{cat}\t{hue}\n")
                total += 1

    print(f"\nWrote {total} entries → {args.output}")

    if all_warnings:
        print("\n⚠  WARNINGS (auto-assigned hues):")
        for w in all_warnings:
            print(f"   • {w}")
    else:
        print("   All categories matched fixed hue tables ✓")


if __name__ == "__main__":
    main()
