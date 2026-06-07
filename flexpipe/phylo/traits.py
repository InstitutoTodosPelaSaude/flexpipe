"""Prepare TreeTime trait metadata with a per-column state cap."""

from __future__ import annotations

import argparse
import logging
import os
import re
from collections import Counter

import pandas as pd

logger = logging.getLogger(__name__)


def _natural_key(value: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _valid_state(value: object) -> bool:
    text = str(value).strip()
    return text not in ("", "nan", "NaN", "NA", "NAN")


def collapse_trait_states(
    df: pd.DataFrame,
    columns: list[str],
    *,
    max_states: int = 200,
    rare_state_label: str = "other",
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Collapse rare categorical states to keep TreeTime trait inference tractable.

    The cap applies independently to every configured trait column.  Empty values
    remain empty; only non-empty states participate in the count and collapse.
    """
    if max_states < 1:
        raise ValueError("max_states must be >= 1")
    rare_state_label = str(rare_state_label).strip()
    if not rare_state_label:
        raise ValueError("rare_state_label must be non-empty")

    out = df.copy()
    log_rows: list[dict[str, object]] = []
    keep_limit = max_states - 1

    for column in columns:
        if column not in out.columns:
            logger.warning("Trait column '%s' not found in metadata; skipping cap", column)
            continue

        values = [str(value).strip() for value in out[column].tolist() if _valid_state(value)]
        counts = Counter(values)
        if len(counts) <= max_states:
            continue

        ranked = sorted(counts.items(), key=lambda item: (-item[1], _natural_key(item[0])))
        collapse = {state for state, _count in ranked[keep_limit:]}

        mask = out[column].astype(str).str.strip().isin(collapse)
        out.loc[mask, column] = rare_state_label

        for state, count in ranked[keep_limit:]:
            log_rows.append(
                {
                    "column": column,
                    "state": state,
                    "count": count,
                    "replacement": rare_state_label,
                }
            )
        logger.info(
            "Collapsed %d rare states in trait '%s' to '%s'",
            len(collapse),
            column,
            rare_state_label,
        )

    return out, log_rows


def write_collapse_log(path: str, rows: list[dict[str, object]]) -> None:
    """Write a TSV log of collapsed states, including a header when empty."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("column\tstate\tcount\treplacement\n")
        for row in rows:
            fh.write(f"{row['column']}\t{row['state']}\t{row['count']}\t{row['replacement']}\n")


def main() -> None:
    """Entry point for ``flexpipe-collapse-traits``."""
    parser = argparse.ArgumentParser(
        description="Write a TreeTime trait metadata sidecar with rare states collapsed"
    )
    parser.add_argument("--metadata", required=True, help="Input metadata TSV")
    parser.add_argument("--output", required=True, help="Output metadata TSV")
    parser.add_argument("--log", required=True, help="Collapsed-state log TSV")
    parser.add_argument("--columns", nargs="+", required=True, help="Trait columns to cap")
    parser.add_argument("--max-states", type=int, default=200)
    parser.add_argument("--rare-state-label", default="other")
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    df = pd.read_csv(args.metadata, sep="\t", dtype=str).fillna("")
    out, rows = collapse_trait_states(
        df,
        args.columns,
        max_states=args.max_states,
        rare_state_label=args.rare_state_label,
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out.to_csv(args.output, sep="\t", index=False)
    write_collapse_log(args.log, rows)
    logger.info("Wrote trait metadata sidecar: %s", args.output)


if __name__ == "__main__":
    main()
