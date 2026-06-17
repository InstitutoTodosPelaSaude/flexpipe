"""Unit tests for flexpipe.phylo.reference_slice."""

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature  # noqa: F401 (used via _feature helpers)
from Bio.SeqRecord import SeqRecord

from flexpipe.phylo.reference_slice import (
    _ensure_cds_feature,
    _ensure_source_feature,
    _find_feature_interval,
    _parse_region,
    slice_reference,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_record(length=1000, features=None, record_id="NC_TEST.1"):
    """Build a minimal GenBank-like SeqRecord."""
    rec = SeqRecord(
        Seq("A" * length),
        id=record_id,
        name=record_id,
        description="test record",
        annotations={"molecule_type": "RNA"},
    )
    rec.features = list(features or [])
    return rec


def _cds(start, end, gene_name="N"):
    return SeqFeature(
        FeatureLocation(start, end, strand=1),
        type="CDS",
        qualifiers={"gene": [gene_name]},
    )


def _gene(start, end, gene_name="N"):
    return SeqFeature(
        FeatureLocation(start, end, strand=1),
        type="gene",
        qualifiers={"gene": [gene_name]},
    )


# ── _parse_region ─────────────────────────────────────────────────────────────


class TestParseRegion:
    def test_valid_region(self):
        assert _parse_region("1233..1682") == (1232, 1682)

    def test_one_based_boundary(self):
        # 1..10 → 0-based half-open (0, 10)
        assert _parse_region("1..10") == (0, 10)

    def test_single_position(self):
        assert _parse_region("100..100") == (99, 100)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid --region"):
            _parse_region("100-200")

    def test_start_zero_raises(self):
        with pytest.raises(ValueError, match="start must be >= 1"):
            _parse_region("0..100")

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError, match="end .* must be >= start"):
            _parse_region("200..100")


# ── _find_feature_interval ────────────────────────────────────────────────────


class TestFindFeatureInterval:
    def test_finds_simple_cds(self):
        record = _make_record(features=[_cds(107, 1685)])
        start, end = _find_feature_interval(record, "N", "CDS")
        assert start == 107
        assert end == 1685

    def test_finds_by_gene_qualifier(self):
        record = _make_record(
            features=[
                _cds(0, 100, "P"),
                _cds(200, 900, "N"),
            ]
        )
        start, end = _find_feature_interval(record, "N", "CDS")
        assert start == 200
        assert end == 900

    def test_raises_when_gene_absent(self):
        record = _make_record(features=[_cds(0, 100, "H")])
        with pytest.raises(ValueError, match=r"No.*feature.*gene.*N"):
            _find_feature_interval(record, "N", "CDS")

    def test_spans_multiple_intervals(self):
        """Compound locations — outer bounding span."""
        record = _make_record(
            features=[
                _cds(100, 200, "N"),
                _cds(300, 500, "N"),
            ]
        )
        # Both intervals are found; min start / max end
        start, end = _find_feature_interval(record, "N", "CDS")
        assert start == 100
        assert end == 500


# ── _ensure_cds_feature ───────────────────────────────────────────────────────


class TestEnsureSourceFeature:
    def test_synthesises_source_when_absent(self):
        rec = _make_record(length=450, features=[_cds(0, 450, "N")])
        assert not any(f.type == "source" for f in rec.features)
        _ensure_source_feature(rec, "Test virus")
        sources = [f for f in rec.features if f.type == "source"]
        assert len(sources) == 1
        assert sources[0].qualifiers["organism"] == ["Test virus"]
        assert int(sources[0].location.start) == 0
        assert int(sources[0].location.end) == 450

    def test_no_op_when_source_present(self):
        from Bio.SeqFeature import FeatureLocation, SeqFeature
        src_feat = SeqFeature(FeatureLocation(0, 450, 1), type="source")
        rec = _make_record(length=450, features=[_cds(0, 450, "N"), src_feat])
        original_count = len(rec.features)
        _ensure_source_feature(rec, "Test virus")
        assert len(rec.features) == original_count

    def test_slice_reference_includes_source_feature(self, tmp_path):
        """slice_reference must synthesise a source feature (BioPython drops
        features that completely span the slice window)."""
        full = _make_record(length=15894, features=[_cds(107, 1685, "N")])
        full.annotations["organism"] = "Test morbillivirus"
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        # N450-like interior slice — BioPython will not carry over the CDS
        # because [107:1685] completely spans [1232:1682].
        sub = slice_reference(src, region="1233..1682", gene="N")
        source_feats = [f for f in sub.features if f.type == "source"]
        assert len(source_feats) == 1
        assert source_feats[0].qualifiers.get("organism") == ["Test morbillivirus"]


class TestEnsureCdsFeature:
    def test_no_op_when_cds_present(self):
        rec = _make_record(features=[_cds(0, 450)])
        original_count = len(rec.features)
        _ensure_cds_feature(rec, "N")
        assert len(rec.features) == original_count

    def test_synthesises_cds_when_absent(self):
        rec = _make_record(length=450, features=[_gene(0, 450)])
        _ensure_cds_feature(rec, "N")
        cds = [f for f in rec.features if f.type == "CDS"]
        assert len(cds) == 1
        assert cds[0].qualifiers["gene"] == ["N"]
        assert int(cds[0].location.start) == 0
        assert int(cds[0].location.end) == 450


# ── slice_reference ───────────────────────────────────────────────────────────


class TestSliceReference:
    def test_slice_by_region(self, tmp_path):
        """Slice a known window and verify length + coordinate reframe."""
        full = _make_record(length=1000, features=[_cds(107, 550, "N")])
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        sub = slice_reference(src, region="108..550")  # 1-based → 107..550
        assert len(sub.seq) == 443
        cds = [f for f in sub.features if f.type == "CDS"]
        assert len(cds) == 1
        # Feature should now start at 0 (reframed to gene-relative coords)
        assert int(cds[0].location.start) == 0
        assert int(cds[0].location.end) == 443

    def test_slice_by_gene(self, tmp_path):
        """Slice using --gene lookup."""
        full = _make_record(length=2000, features=[_cds(500, 950, "H"), _cds(100, 500, "N")])
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        sub = slice_reference(src, gene="N", feature_type="CDS")
        assert len(sub.seq) == 400  # 500 - 100

    def test_new_id_is_set(self, tmp_path):
        full = _make_record(features=[_cds(0, 100)])
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        sub = slice_reference(src, region="1..100", new_id="CUSTOM_ID")
        assert sub.id == "CUSTOM_ID"

    def test_default_id_kept(self, tmp_path):
        full = _make_record(record_id="NC_ORIG.1", features=[_cds(0, 100)])
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        sub = slice_reference(src, region="1..100")
        assert sub.id == "NC_ORIG.1"

    def test_molecule_type_preserved(self, tmp_path):
        full = _make_record(features=[_cds(0, 100)])
        full.annotations["molecule_type"] = "cRNA"
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        sub = slice_reference(src, region="1..100")
        assert sub.annotations["molecule_type"] == "cRNA"

    def test_raises_without_region_or_gene(self, tmp_path):
        full = _make_record(features=[_cds(0, 100)])
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        with pytest.raises(ValueError, match="Provide --region or --gene"):
            slice_reference(src)

    def test_region_beyond_length_raises(self, tmp_path):
        full = _make_record(length=100, features=[_cds(0, 100)])
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        with pytest.raises(ValueError, match="Slice end .* exceeds reference length"):
            slice_reference(src, region="1..200")

    def test_round_trip_genbank(self, tmp_path):
        """Write the sliced record to GenBank and read it back."""
        full = _make_record(length=2000, features=[_cds(1232, 1682, "N")])
        src = tmp_path / "full.gb"
        SeqIO.write(full, str(src), "genbank")

        sub = slice_reference(src, region="1233..1682", gene="N")
        out = tmp_path / "slice.gb"
        SeqIO.write(sub, str(out), "genbank")

        re_read = SeqIO.read(str(out), "genbank")
        assert len(re_read.seq) == 450
        assert any(f.type == "CDS" for f in re_read.features)

    def test_n450_measles_reference(self):
        """Integration test: slice N450 from the bundled measles reference.gb."""
        from pathlib import Path

        ref_path = Path("builds/measles-b3-global/reference.gb")
        if not ref_path.exists():
            pytest.skip("measles reference.gb not found")

        sub = slice_reference(
            ref_path,
            region="1233..1682",
            gene="N",
            new_id="NC_001498.1",
        )
        assert len(sub.seq) == 450
        assert sub.id == "NC_001498.1"
        cds = [f for f in sub.features if f.type == "CDS"]
        assert len(cds) == 1
        assert cds[0].qualifiers.get("gene") == ["N"]
