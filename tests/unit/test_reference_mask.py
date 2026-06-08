"""Unit tests for reference-derived terminal BED masks."""

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from flexpipe.phylo.reference_mask import derive_terminal_masks, load_mask_profile


def _record(length=100, features=None):
    return SeqRecord(Seq("A" * length), id="REF", features=list(features or []))


def _feature(feature_type, start, end, **qualifiers):
    return SeqFeature(FeatureLocation(start, end), type=feature_type, qualifiers=qualifiers)


def _coords(intervals):
    return [(item.start, item.end, item.reason) for item in intervals]


def test_explicit_terminal_utr_features_win():
    profile = load_mask_profile()
    record = _record(
        features=[
            _feature("5'UTR", 0, 10),
            _feature("CDS", 10, 90),
            _feature("3'UTR", 90, 100),
        ]
    )

    intervals = derive_terminal_masks(record, profile)

    assert _coords(intervals) == [(0, 10, "5'UTR:5prime"), (90, 100, "3'UTR:3prime")]


def test_utr_like_qualifiers_on_gene_and_misc_feature_are_detected():
    profile = load_mask_profile()
    record = _record(
        features=[
            _feature("gene", 0, 8, note=["5 prime untranslated region"]),
            _feature("CDS", 8, 92),
            _feature("misc_feature", 92, 100, note=["trailer"]),
        ]
    )

    intervals = derive_terminal_masks(record, profile)

    assert _coords(intervals) == [(0, 8, "gene:5prime"), (92, 100, "misc_feature:3prime")]


def test_cds_boundary_fallback_masks_terminal_non_coding_regions():
    profile = load_mask_profile()
    record = _record(features=[_feature("CDS", 12, 88)])

    intervals = derive_terminal_masks(record, profile)

    assert _coords(intervals) == [
        (0, 12, "CDS:5prime_boundary"),
        (88, 100, "CDS:3prime_boundary"),
    ]


def test_gene_boundary_fallback_when_cds_absent():
    profile = load_mask_profile()
    record = _record(features=[_feature("gene", 5, 95)])

    intervals = derive_terminal_masks(record, profile)

    assert _coords(intervals) == [
        (0, 5, "gene:5prime_boundary"),
        (95, 100, "gene:3prime_boundary"),
    ]


def test_full_genome_misc_feature_is_ignored_for_boundary_fallback():
    profile = load_mask_profile()
    record = _record(
        features=[
            _feature("misc_feature", 0, 100, note=["complete genome"]),
            _feature("CDS", 10, 90),
        ]
    )

    intervals = derive_terminal_masks(record, profile)

    assert _coords(intervals) == [
        (0, 10, "CDS:5prime_boundary"),
        (90, 100, "CDS:3prime_boundary"),
    ]


def test_guardrail_returns_empty_masks_when_too_much_reference_would_be_masked():
    profile = {**load_mask_profile(), "max_mask_fraction": 0.1}
    record = _record(features=[_feature("CDS", 40, 60)])

    assert derive_terminal_masks(record, profile) == []
