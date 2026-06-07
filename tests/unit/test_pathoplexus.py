"""Unit tests for flexpipe.ingest.pathoplexus — HTTP-mock tests via `responses`."""

from urllib.parse import parse_qs, urlparse

import pytest
import responses as resp_lib

from flexpipe.ingest.pathoplexus import (
    base_params,
    build_url,
    fetch_metadata,
    fetch_sequences,
    normalize_fasta_entry_id,
)


class TestBuildUrl:
    def test_constructs_url(self):
        url = build_url("https://lapis.example.com", "YFV", "details")
        assert url == "https://lapis.example.com/YFV/sample/details"

    def test_strips_trailing_slash(self):
        url = build_url("https://lapis.example.com/", "YFV", "details")
        assert url == "https://lapis.example.com/YFV/sample/details"


class TestBaseParams:
    def test_no_filters(self):
        p = base_params(None, None)
        assert p == {"versionStatus": "LATEST_VERSION"}

    def test_min_date_included(self):
        p = base_params("2020-01-01", None)
        assert p["sampleCollectionDateRangeLowerFrom"] == "2020-01-01"

    def test_min_completeness_included(self):
        p = base_params(None, 0.80)
        assert p["completenessFrom"] == 0.80

    def test_max_date_included(self):
        p = base_params(None, None, max_date="2026-06-06")
        assert p["sampleCollectionDateRangeUpperTo"] == "2026-06-06"

    def test_query_params_are_included(self):
        p = base_params(
            None,
            None,
            query_params={"serotype": "DENV-1", "dataUseTerms": "OPEN"},
        )
        assert p["serotype"] == "DENV-1"
        assert p["dataUseTerms"] == "OPEN"

    def test_empty_query_params_are_ignored(self):
        p = base_params(None, None, query_params={"serotype": "", "country": None})
        assert "serotype" not in p
        assert "country" not in p

    def test_core_params_override_conflicting_query_params(self):
        p = base_params(
            "2020-01-01",
            0.70,
            max_date="2026-06-06",
            query_params={
                "versionStatus": "REVOKED",
                "sampleCollectionDateRangeLowerFrom": "1990-01-01",
                "sampleCollectionDateRangeUpperTo": "1999-01-01",
                "completenessFrom": 0.1,
            },
        )
        assert p["versionStatus"] == "LATEST_VERSION"
        assert p["sampleCollectionDateRangeLowerFrom"] == "2020-01-01"
        assert p["sampleCollectionDateRangeUpperTo"] == "2026-06-06"
        assert p["completenessFrom"] == 0.70


class TestFetchMetadata:
    _URL = "https://lapis.test/YFV/sample/details"

    def _query_for_call(self, index: int = 0):
        return parse_qs(urlparse(resp_lib.calls[index].request.url).query)

    @resp_lib.activate
    def test_single_page(self):
        body = "accessionVersion\thost\nABC123\tHomo sapiens\n"
        resp_lib.add(resp_lib.GET, self._URL, body=body, status=200)
        header, rows = fetch_metadata(self._URL, chunk_size=10000)
        assert header == "accessionVersion\thost"
        assert len(rows) == 1
        assert "ABC123" in rows[0]

    @resp_lib.activate
    def test_pagination_two_pages(self):
        # First page — full chunk (size=2)
        page1 = "col\nrow1\nrow2\n"
        page2 = "col\nrow3\n"
        resp_lib.add(resp_lib.GET, self._URL, body=page1, status=200)
        resp_lib.add(resp_lib.GET, self._URL, body=page2, status=200)
        header, rows = fetch_metadata(self._URL, chunk_size=2)
        assert header == "col"
        assert len(rows) == 3

    @resp_lib.activate
    def test_empty_response_returns_none_header(self):
        resp_lib.add(resp_lib.GET, self._URL, body="", status=200)
        header, rows = fetch_metadata(self._URL)
        assert header is None
        assert rows == []

    @resp_lib.activate
    def test_auth_token_sent_as_bearer(self):
        resp_lib.add(resp_lib.GET, self._URL, body="col\nrow\n", status=200)
        fetch_metadata(self._URL, auth_token="secret")
        sent_headers = resp_lib.calls[0].request.headers
        assert sent_headers.get("Authorization") == "Bearer secret"

    @resp_lib.activate
    def test_query_params_sent(self):
        resp_lib.add(resp_lib.GET, self._URL, body="col\nrow\n", status=200)
        fetch_metadata(
            self._URL,
            query_params={"serotype": "DENV-1", "dataUseTerms": "OPEN"},
        )
        query = self._query_for_call()
        assert query["serotype"] == ["DENV-1"]
        assert query["dataUseTerms"] == ["OPEN"]

    @resp_lib.activate
    def test_query_params_survive_pagination(self):
        page1 = "col\nrow1\nrow2\n"
        page2 = "col\nrow3\n"
        resp_lib.add(resp_lib.GET, self._URL, body=page1, status=200)
        resp_lib.add(resp_lib.GET, self._URL, body=page2, status=200)
        fetch_metadata(
            self._URL,
            chunk_size=2,
            query_params={"serotype": "DENV-2", "dataUseTerms": "OPEN"},
        )
        query = self._query_for_call(1)
        assert query["serotype"] == ["DENV-2"]
        assert query["dataUseTerms"] == ["OPEN"]
        assert query["offset"] == ["2"]

    @resp_lib.activate
    def test_http_error_raises(self):
        import requests

        resp_lib.add(resp_lib.GET, self._URL, status=500)
        with pytest.raises(requests.HTTPError):
            fetch_metadata(self._URL)


class TestFetchSequences:
    _URL = "https://lapis.test/YFV/sample/unalignedNucleotideSequences"

    def _query_for_call(self, index: int = 0):
        return parse_qs(urlparse(resp_lib.calls[index].request.url).query)

    @resp_lib.activate
    def test_single_page(self):
        body = ">SEQ001\nACGT\n>SEQ002\nTTTT\n"
        resp_lib.add(resp_lib.GET, self._URL, body=body, status=200)
        entries = fetch_sequences(self._URL, chunk_size=10000)
        assert len(entries) == 2

    @resp_lib.activate
    def test_empty_response(self):
        resp_lib.add(resp_lib.GET, self._URL, body="", status=200)
        entries = fetch_sequences(self._URL)
        assert entries == []

    @resp_lib.activate
    def test_query_params_sent(self):
        resp_lib.add(resp_lib.GET, self._URL, body=">SEQ001\nACGT\n", status=200)
        fetch_sequences(
            self._URL,
            query_params={"serotype": "DENV-3", "dataUseTerms": "OPEN"},
        )
        query = self._query_for_call()
        assert query["serotype"] == ["DENV-3"]
        assert query["dataUseTerms"] == ["OPEN"]

    @resp_lib.activate
    def test_query_params_survive_pagination(self):
        page1 = ">SEQ001\nACGT\n>SEQ002\nTTTT\n"
        page2 = ">SEQ003\nGGGG\n"
        resp_lib.add(resp_lib.GET, self._URL, body=page1, status=200)
        resp_lib.add(resp_lib.GET, self._URL, body=page2, status=200)
        fetch_sequences(
            self._URL,
            chunk_size=2,
            query_params={"serotype": "DENV-4", "dataUseTerms": "OPEN"},
        )
        query = self._query_for_call(1)
        assert query["serotype"] == ["DENV-4"]
        assert query["dataUseTerms"] == ["OPEN"]
        assert query["offset"] == ["2"]


class TestNormalizeFastaEntryId:
    def test_noop_when_disabled(self):
        entry = "PP_001|DENV-1\nACGT\n"
        assert normalize_fasta_entry_id(entry) == entry

    def test_strips_pipe_suffix_from_header(self):
        entry = "PP_001|DENV-1\nACGT"
        assert normalize_fasta_entry_id(entry, strip_pipe_suffix=True) == "PP_001\nACGT"

    def test_preserves_sequence_lines_and_trailing_newline(self):
        entry = "PP_001|DENV-1\nACGT\nTTTT\n"
        assert normalize_fasta_entry_id(entry, strip_pipe_suffix=True) == "PP_001\nACGT\nTTTT\n"
