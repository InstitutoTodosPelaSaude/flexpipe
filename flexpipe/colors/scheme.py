"""
Hex colour scheme generation from hue tables.

Assigns hex colours per metadata value by sampling a matplotlib colormap
gradient between a base hue and its neighbouring hues.

Extracted from ``scripts/colour_maker.py``.

Key changes vs the original:
- ``from pylab import *`` removed; explicit imports only.
- ``cm.get_cmap(name)`` replaced with ``matplotlib.colormaps[name]``
  (``get_cmap`` was removed in matplotlib 3.9).
- ``cm.get_cmap(name, N)`` replaced with ``matplotlib.colormaps[name].resampled(N)``.
- All logic lifted out of ``if __name__ == '__main__'`` into importable functions.
- Wrong argparse description corrected.
- Commented-out personal absolute paths removed.
- ``print()`` replaced with ``logging``.
"""

import argparse
import hashlib
import logging

import matplotlib.colors
import pandas as pd
from colour import Color

logger = logging.getLogger(__name__)


# Hue → (dark_hex, light_hex) mapping used for the gradient endpoints.
# Covers every 10-degree step of the hue wheel (0–350).
HUE_TO_HEX = {
    0: ("#660000", "#F5D6D6"),
    10: ("#661100", "#F5DBD6"),
    20: ("#662200", "#F5E0D6"),
    30: ("#663300", "#F5E6D6"),
    40: ("#664400", "#F5EBD6"),
    50: ("#665500", "#F5F0D6"),
    60: ("#666600", "#F5F5D6"),
    70: ("#556600", "#F0F5D6"),
    80: ("#446600", "#EBF5D6"),
    90: ("#336600", "#E6F5D6"),
    100: ("#226600", "#E0F5D6"),
    110: ("#116600", "#DBF5D6"),
    120: ("#006600", "#D6F5D6"),
    130: ("#006611", "#D6F5DB"),
    140: ("#006622", "#D6F5E0"),
    150: ("#006633", "#D6F5E6"),
    160: ("#006644", "#D6F5EB"),
    170: ("#006655", "#D6F5F0"),
    180: ("#006666", "#D6F5F5"),
    190: ("#005566", "#D6F0F5"),
    200: ("#004466", "#D6EBF5"),
    210: ("#003366", "#D6E6F5"),
    220: ("#002266", "#D6E0F5"),
    230: ("#001166", "#D6DBF5"),
    240: ("#000066", "#D6D6F5"),
    250: ("#110066", "#DBD6F5"),
    260: ("#220066", "#E0D6F5"),
    270: ("#330066", "#E6D6F5"),
    280: ("#440066", "#EBD6F5"),
    290: ("#550066", "#F0D6F5"),
    300: ("#660066", "#F5D6F5"),
    310: ("#660055", "#F5D6F0"),
    320: ("#660044", "#F5D6EB"),
    330: ("#660033", "#F5D6E6"),
    340: ("#660022", "#F5D6E0"),
    350: ("#660011", "#F5D6DB"),
}


def load_hue_table(path: str) -> dict:
    """Load a ``category → hue`` TSV and return a dict.

    The TSV has columns ``category`` and ``hue``; the ``hue`` value is either
    an integer (0–350) or a matplotlib colormap name.
    """
    df = pd.read_csv(path, sep="\t", dtype=str, comment="#").fillna("")
    result = {}
    for _, row in df.iterrows():
        key = str(row.get("category", "")).strip()
        val = str(row.get("hue", "")).strip()
        if key and val:
            result[key] = val
    return result


def linear_gradient(start_hex: str, finish_hex: str, n: int) -> list:
    """Return a list of *n* hex colour strings interpolated between two hex colours.

    Args:
        start_hex: Starting hex colour (e.g. ``"#004466"``).
        finish_hex: Ending hex colour.
        n: Number of colours in the gradient.

    Returns:
        List of *n* lowercase hex colour strings.
    """
    start = Color(start_hex)
    end = Color(finish_hex)
    return [c.hex_l for c in start.range_to(end, n)]


def _colormap_sample(cmap_name: str, n_members: int) -> list:
    """Sample *n_members* evenly-spaced hex colours from a named matplotlib colormap.

    Replaces the old ``cm.get_cmap(name, N)`` pattern which was removed in
    matplotlib 3.9.

    Args:
        cmap_name: A registered matplotlib colormap name (e.g. ``"Blues_r"``).
        n_members: Number of distinct colours needed.

    Returns:
        List of hex colour strings.
    """
    cmap = matplotlib.colormaps[cmap_name].resampled(n_members + 4)
    return [
        matplotlib.colors.rgb2hex(cmap(i)) for i in range(2, cmap.N - 2)  # skip the extreme ends
    ]


def _stable_shade_index(*parts: str, slots: int = 101) -> int:
    """Return a deterministic non-extreme gradient index for a hierarchy member."""
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return 5 + (int(digest, 16) % max(1, slots - 10))


def _stable_member_colour(hue_val: str, root: str, level: str, member: str) -> str:
    """Assign a stable shade within a root hue family."""
    idx = _stable_shade_index(root, level, member)
    if str(hue_val).isdigit():
        start, end = HUE_TO_HEX[int(hue_val)]
        return linear_gradient(start, end, 101)[idx]

    colours = _colormap_sample(str(hue_val), 101)
    return colours[min(idx, len(colours) - 1)]


def _root_colour(hue_val: str) -> str:
    if str(hue_val).isdigit():
        start, end = HUE_TO_HEX[int(hue_val)]
        return linear_gradient(start, end, 11)[3]
    return _colormap_sample(str(hue_val), 1)[0]


def build_scheme(
    df: pd.DataFrame,
    levels: list,
    colour_wheel: dict,
) -> dict:
    """Compute ``{level: {value: hex_colour}}`` for all hierarchy levels.

    Args:
        df: Metadata DataFrame containing the columns named in *levels*.
        levels: Ordered list of column names (most → least specific).
        colour_wheel: ``{top_level_value: hue_or_cmap_name}`` from the hue TSV.

    Returns:
        Nested dict ``{level_name: {value_name: hex_colour}}``.
    """
    results: dict[str, dict[str, str]] = {level: {} for level in levels}

    for highest, dfG in df[levels].groupby(levels[0], as_index=False):
        dfG = dfG.drop_duplicates().sort_values(by=levels)
        hue_val = colour_wheel.get(str(highest), "")
        if not hue_val:
            logger.warning("No hue configured for hierarchy root '%s'", highest)
            continue

        for level in levels:
            members = dfG[level].drop_duplicates().tolist()
            for member in members:
                if str(member).strip() == "":
                    continue
                if level == levels[0]:
                    results[level][member] = _root_colour(str(hue_val))
                else:
                    results[level][member] = _stable_member_colour(
                        str(hue_val), str(highest), level, str(member)
                    )

    return results


def find_polymorphic_root(levels: list[str], df: pd.DataFrame, min_distinct: int = 2) -> str:
    """Return the first level in *levels* that has ≥ *min_distinct* distinct non-empty values.

    Falls back to the first level if none qualify (degenerate dataset).
    """
    for col in levels:
        if col not in df.columns:
            continue
        distinct = df[col].replace("", pd.NA).dropna().nunique()
        if distinct >= min_distinct:
            return col
    return levels[0]


def effective_levels(
    levels: list[str],
    root_level: str | None,
    detect_from: str | None,
) -> list[str]:
    """Return the trimmed levels list starting from the effective root.

    Args:
        levels: Full ordered levels list from config.
        root_level: Explicit root column name (``"auto"`` triggers detection).
        detect_from: Path to the full corpus metadata TSV used for auto-detection.

    Returns:
        Trimmed list; prefix levels before the effective root are dropped.
    """
    if not root_level:
        return levels

    if root_level == "auto":
        if not detect_from:
            logger.warning("clade_root_level=auto but --detect-root-from not provided; using full levels")
            return levels
        detect_df = pd.read_csv(detect_from, sep="\t", dtype=str).fillna("")
        root = find_polymorphic_root(levels, detect_df)
    else:
        if root_level not in levels:
            logger.warning("clade_root_level=%r not in levels %s; using full levels", root_level, levels)
            return levels
        root = root_level

    idx = levels.index(root)
    if idx > 0:
        dropped = levels[:idx]
        logger.info(
            "clade_root_level: dropping monomorphic prefix %s; root = %r",
            dropped,
            root,
        )
    return levels[idx:]


def main() -> None:
    """Entry point for ``flexpipe-colours``."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate a colour scheme TSV (field/value/hex_color) from metadata " "and a hue table."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Metadata TSV with categorical data")
    parser.add_argument("--colours", required=True, help="TSV with top-level category hues")
    parser.add_argument(
        "--levels",
        required=True,
        nargs="+",
        type=str,
        help="Column names in hierarchical order (most → least specific)",
    )
    parser.add_argument("--output", required=True, help="Output colour scheme TSV")
    parser.add_argument(
        "--root-level",
        default="",
        help=(
            "Trim monomorphic prefix levels. "
            "'auto' detects from --detect-root-from; otherwise a specific column name."
        ),
    )
    parser.add_argument(
        "--detect-root-from",
        default="",
        help="Path to the full corpus metadata TSV for auto root detection (used with --root-level auto).",
    )
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    df = pd.read_csv(args.input, sep="\t", dtype=str).fillna("")

    levels = effective_levels(
        args.levels,
        root_level=args.root_level or None,
        detect_from=args.detect_root_from or None,
    )

    df = df[~df[levels[0]].isin([""])]

    colour_wheel = load_hue_table(args.colours)
    results = build_scheme(df, levels, colour_wheel)

    with open(args.output, "w") as fh:
        fh.write("field\tvalue\thex_color\n")
        for trait, entries in results.items():
            for place, hexcolour in entries.items():
                fh.write(f"{trait}\t{place}\t{hexcolour.upper()}\n")
            fh.write("\n")

    logger.info("Colour file successfully created: %s", args.output)


if __name__ == "__main__":
    main()
