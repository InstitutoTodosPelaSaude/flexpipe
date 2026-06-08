"""Generate terminal reference-mask BED files from GenBank annotations."""

from __future__ import annotations

import argparse
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Bio import SeqIO
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature

from flexpipe.data import load_data_yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MaskInterval:
    """A BED-style mask interval."""

    start: int
    end: int
    reason: str

    @property
    def length(self) -> int:
        return max(self.end - self.start, 0)


def load_mask_profile(
    override: str | Path | None = None, profile: str = "default"
) -> dict[str, Any]:
    """Load a bundled or overridden reference-mask profile."""
    data = load_data_yaml("flexpipe.data.phylo", "reference_mask_profiles.yaml", override=override)
    if not isinstance(data, dict):
        raise ValueError("Reference-mask profiles must be a YAML mapping")
    selected = data.get(profile)
    if not isinstance(selected, dict):
        raise ValueError(f"Reference-mask profile not found or invalid: {profile}")
    return selected


def _feature_intervals(feature: SeqFeature) -> list[tuple[int, int]]:
    loc = feature.location
    parts: Iterable[FeatureLocation]
    if isinstance(loc, CompoundLocation):
        parts = loc.parts
    else:
        parts = [loc]
    intervals = []
    for part in parts:
        intervals.append((int(part.start), int(part.end)))
    return intervals


def _is_full_length(start: int, end: int, length: int) -> bool:
    return start <= 0 and end >= length


def _qualifier_text(feature: SeqFeature, keys: list[str]) -> str:
    values: list[str] = []
    for key in keys:
        for value in feature.qualifiers.get(key, []):
            values.append(str(value))
    return " ".join(values)


def _is_utr_like(feature: SeqFeature, profile: dict[str, Any]) -> bool:
    feature_type = str(feature.type)
    explicit = {str(value).casefold() for value in profile.get("explicit_feature_types", [])}
    if feature_type.casefold() in explicit:
        return True

    qualifier_types = {
        str(value).casefold() for value in profile.get("qualifier_feature_types", [])
    }
    if feature_type.casefold() not in qualifier_types:
        return False

    text = _qualifier_text(feature, list(profile.get("qualifier_keys", [])))
    if not text.strip():
        return False
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in profile["utr_patterns"])


def _terminal_utr_masks(record, profile: dict[str, Any]) -> list[MaskInterval]:
    length = len(record.seq)
    intervals: list[MaskInterval] = []
    for feature in record.features:
        if not _is_utr_like(feature, profile):
            continue
        for start, end in _feature_intervals(feature):
            if _is_full_length(start, end, length):
                continue
            if start <= 0:
                intervals.append(MaskInterval(0, min(end, length), f"{feature.type}:5prime"))
            elif end >= length:
                intervals.append(MaskInterval(max(start, 0), length, f"{feature.type}:3prime"))
    return intervals


def _boundary_feature_intervals(record, feature_type: str) -> list[tuple[int, int]]:
    length = len(record.seq)
    intervals = []
    for feature in record.features:
        if str(feature.type) != feature_type:
            continue
        for start, end in _feature_intervals(feature):
            if _is_full_length(start, end, length):
                continue
            if start < end:
                intervals.append((max(start, 0), min(end, length)))
    return intervals


def _boundary_masks(record, profile: dict[str, Any]) -> list[MaskInterval]:
    length = len(record.seq)
    for feature_type in profile.get("boundary_feature_priority", []):
        intervals = _boundary_feature_intervals(record, str(feature_type))
        if not intervals:
            continue
        first_start = min(start for start, _end in intervals)
        last_end = max(end for _start, end in intervals)
        masks = []
        if first_start > 0:
            masks.append(MaskInterval(0, first_start, f"{feature_type}:5prime_boundary"))
        if last_end < length:
            masks.append(MaskInterval(last_end, length, f"{feature_type}:3prime_boundary"))
        return masks
    return []


def _merge_intervals(intervals: list[MaskInterval]) -> list[MaskInterval]:
    clean = sorted((i for i in intervals if i.start < i.end), key=lambda i: (i.start, i.end))
    if not clean:
        return []
    merged = [clean[0]]
    for interval in clean[1:]:
        last = merged[-1]
        if interval.start <= last.end:
            merged[-1] = MaskInterval(
                start=last.start,
                end=max(last.end, interval.end),
                reason=f"{last.reason};{interval.reason}",
            )
        else:
            merged.append(interval)
    return merged


def derive_terminal_masks(record, profile: dict[str, Any]) -> list[MaskInterval]:
    """Derive terminal mask intervals for a GenBank record."""
    length = len(record.seq)
    utr_masks = _terminal_utr_masks(record, profile)
    boundary_masks = _boundary_masks(record, profile)

    has_5prime = any(interval.start == 0 for interval in utr_masks)
    has_3prime = any(interval.end == length for interval in utr_masks)
    masks = list(utr_masks)
    for interval in boundary_masks:
        if interval.start == 0 and has_5prime:
            continue
        if interval.end == length and has_3prime:
            continue
        masks.append(interval)

    merged = _merge_intervals(masks)
    max_fraction = float(profile.get("max_mask_fraction", 0.25))
    masked_fraction = sum(interval.length for interval in merged) / max(length, 1)
    if masked_fraction > max_fraction:
        logger.warning(
            "Reference mask covers %.1f%% of %s; exceeds max %.1f%%, writing no masks",
            masked_fraction * 100,
            record.id,
            max_fraction * 100,
        )
        return []
    return merged


def write_bed(record_id: str, intervals: list[MaskInterval], output: str | Path) -> None:
    """Write BED intervals without a header."""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for interval in intervals:
            fh.write(f"{record_id}\t{interval.start}\t{interval.end}\t{interval.reason}\n")


def main() -> None:
    """Entry point for ``flexpipe-reference-mask``."""
    parser = argparse.ArgumentParser(description="Generate terminal BED masks from reference.gb")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--profile-file", default="")
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()
    profile = load_mask_profile(args.profile_file or None, profile=args.profile)
    record = SeqIO.read(args.reference, "genbank")
    intervals = derive_terminal_masks(record, profile)
    write_bed(record.id, intervals, args.output)
    logger.info("Wrote %d reference mask intervals to %s", len(intervals), args.output)


if __name__ == "__main__":
    main()
