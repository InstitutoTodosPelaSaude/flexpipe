"""Unit tests for flexpipe.ingest.ncbi — parsing helpers."""

from unittest.mock import MagicMock

from flexpipe.ingest.ncbi import parse_country_field, parse_gb_record, search_ncbi


class TestParseCountryField:
    def test_country_only(self):
        c, d, loc = parse_country_field("Brazil")
        assert c == "Brazil"
        assert d == ""
        assert loc == ""

    def test_country_and_division(self):
        c, d, loc = parse_country_field("Brazil: Amazonas")
        assert c == "Brazil"
        assert d == "Amazonas"
        assert loc == ""

    def test_country_division_location(self):
        c, d, loc = parse_country_field("Brazil: São Paulo, Santos")
        assert c == "Brazil"
        assert d == "São Paulo"
        assert loc == "Santos"

    def test_empty_string(self):
        c, d, loc = parse_country_field("")
        assert c == d == loc == ""

    def test_strips_whitespace(self):
        c, d, loc = parse_country_field("  USA : California , Los Angeles  ")
        assert c == "USA"
        assert d == "California"
        assert loc == "Los Angeles"


class TestParseGbRecord:
    def _make_record(self, *, host="", country="", collection_date="", authors_str=""):
        """Build a minimal mock BioPython SeqRecord."""
        feature = MagicMock()
        feature.type = "source"
        # BioPython qualifiers never have empty lists — absent key means absent value
        qualifiers = {}
        if host:
            qualifiers["host"] = [host]
        if country:
            qualifiers["geo_loc_name"] = [country]
        if collection_date:
            qualifiers["collection_date"] = [collection_date]
        feature.qualifiers = qualifiers

        ref = MagicMock()
        ref.authors = authors_str

        rec = MagicMock()
        rec.id = "MK123456.1"
        rec.features = [feature]
        rec.annotations = {"references": [ref]}
        return rec

    def test_basic_fields_extracted(self):
        rec = self._make_record(
            host="Homo sapiens", country="Brazil: São Paulo", collection_date="2022-03"
        )
        result = parse_gb_record(rec)
        assert result["accessionVersion"] == "MK123456.1"
        assert result["hostNameCommon"] == "Homo sapiens"
        assert result["geoLocCountry"] == "Brazil"
        assert result["geoLocAdmin1"] == "São Paulo"
        assert result["sampleCollectionDate"] == "2022-03"

    def test_data_use_always_open(self):
        rec = self._make_record()
        assert parse_gb_record(rec)["dataUseTerms"] == "OPEN"

    def test_lineage_always_empty(self):
        rec = self._make_record()
        assert parse_gb_record(rec)["lineage"] == ""

    def test_source_always_ncbi(self):
        rec = self._make_record()
        assert parse_gb_record(rec)["source"] == "NCBI"

    def test_authors_et_al_format(self):
        rec = self._make_record(authors_str="Smith, John, Doe, Jane")
        result = parse_gb_record(rec)
        assert result["authors"] == "Smith et al"

    def test_missing_host_gives_empty(self):
        rec = self._make_record(host="")
        assert parse_gb_record(rec)["hostNameCommon"] == ""


class TestSearchNcbi:
    def test_run_date_bounds_publication_date_query(self, monkeypatch):
        captured = {}

        class Handle:
            def close(self):
                pass

        def fake_esearch(**kwargs):
            captured["term"] = kwargs["term"]
            return Handle()

        monkeypatch.setattr("flexpipe.ingest.ncbi.Entrez.esearch", fake_esearch)
        monkeypatch.setattr(
            "flexpipe.ingest.ncbi.Entrez.read",
            lambda handle: {"Count": "0", "WebEnv": "we", "QueryKey": "qk"},
        )

        search_ncbi(11089, 7000, 12000, min_date="2020-01-01", max_date="2026-06-06")

        assert "2020/01/01:2026/06/06[PDAT]" in captured["term"]
