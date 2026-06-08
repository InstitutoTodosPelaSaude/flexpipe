"""Normalize flexible collection-date strings before Augur date curation."""

from __future__ import annotations

import argparse
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from flexpipe.data import load_data_yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DateResult:
    """Normalized date value and status metadata."""

    value: str
    status: str
    reason: str = ""


def load_date_policy(override: str | Path | None = None) -> dict[str, Any]:
    """Load bundled date-format policy or a build-specific override."""
    data = load_data_yaml("flexpipe.data.curation", "date_formats.yaml", override=override)
    if not isinstance(data, dict):
        raise ValueError("Date-format policy must be a YAML mapping")
    return data


def _missing_values(policy: dict[str, Any]) -> set[str]:
    return {str(v).casefold().strip() for v in policy.get("missing_values", [])}


def _format_date(dt: datetime, precision: str) -> str:
    if precision == "year":
        return f"{dt.year:04d}"
    if precision == "year_month":
        return f"{dt.year:04d}-{dt.month:02d}"
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"


def _parse_with_formats(value: str, formats: list[str], precision: str) -> DateResult | None:
    for fmt in formats:
        try:
            return DateResult(_format_date(datetime.strptime(value, fmt), precision), "normalized")
        except ValueError:
            continue
    return None


def _slash_ambiguity(value: str, slash_order: str) -> DateResult | None:
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if not match:
        return None
    first, second, year = (int(part) for part in match.groups())
    ambiguous = 1 <= first <= 12 and 1 <= second <= 12 and first != second
    order = str(slash_order or "MDY").upper()
    if order == "DMY":
        month, day = second, first
    else:
        month, day = first, second
    try:
        parsed = datetime(year, month, day)
    except ValueError:
        return DateResult("", "invalid", "impossible slash date")
    status = "ambiguous" if ambiguous else "normalized"
    reason = f"slash date interpreted as {order}" if ambiguous else ""
    return DateResult(_format_date(parsed, "full_date"), status, reason)


def normalize_date(value: object, policy: dict[str, Any]) -> DateResult:
    """Normalize one collection-date value.

    Returns an empty value with status ``invalid`` for impossible dates, and
    ``missing`` for configured sentinel values. Partial dates keep their precision.
    """
    text = str(value or "").strip()
    if text.casefold() in _missing_values(policy):
        return DateResult("", "missing", "configured missing value")
    if text.casefold().split(":", 1)[0].strip() in _missing_values(policy):
        return DateResult("", "missing", "configured missing prefix")
    if not text:
        return DateResult("", "missing", "blank")

    formats = policy.get("formats", {}) or {}
    slash = _slash_ambiguity(text, str(policy.get("slash_order", "MDY")))
    if slash is not None:
        return slash

    for precision in ("year", "year_month", "full_date"):
        result = _parse_with_formats(text, list(formats.get(precision, [])), precision)
        if result is not None:
            return result

    return DateResult("", "invalid", "unrecognized date format")


def normalize_dates_table(
    df: pd.DataFrame,
    *,
    date_field: str,
    policy: dict[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Normalize a metadata table and return changed/problem rows for logging."""
    out = df.copy()
    if date_field not in out.columns:
        raise ValueError(f"Date field not found in metadata: {date_field}")

    log_rows: list[dict[str, str]] = []
    normalized_values: list[str] = []
    for idx, raw in out[date_field].items():
        result = normalize_date(raw, policy)
        normalized_values.append(result.value)
        if result.status != "normalized" or str(raw).strip() != result.value:
            log_rows.append(
                {
                    "row": str(idx),
                    "original": str(raw),
                    "normalized": result.value,
                    "status": result.status,
                    "reason": result.reason,
                }
            )
    out[date_field] = normalized_values
    return out, log_rows


def write_date_log(path: str | Path, rows: list[dict[str, str]]) -> None:
    """Write a TSV log for date normalization."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        fh.write("row\toriginal\tnormalized\tstatus\treason\n")
        for row in rows:
            fh.write(
                f"{row['row']}\t{row['original']}\t{row['normalized']}\t"
                f"{row['status']}\t{row['reason']}\n"
            )


def main() -> None:
    """Entry point for ``flexpipe-normalize-dates``."""
    parser = argparse.ArgumentParser(description="Normalize flexible metadata date strings")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--date-field", default="date")
    parser.add_argument("--policy", default="")
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()
    policy = load_date_policy(args.policy or None)
    df = pd.read_csv(args.metadata, sep="\t", dtype=str, keep_default_na=False).fillna("")
    out, rows = normalize_dates_table(df, date_field=args.date_field, policy=policy)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out.to_csv(args.output, sep="\t", index=False)
    write_date_log(args.log, rows)
    problem_count = sum(1 for row in rows if row["status"] in {"invalid", "ambiguous"})
    if problem_count:
        logger.warning("Date normalization logged %d invalid/ambiguous rows", problem_count)
    logger.info("Wrote normalized metadata dates: %s", args.output)


if __name__ == "__main__":
    main()
