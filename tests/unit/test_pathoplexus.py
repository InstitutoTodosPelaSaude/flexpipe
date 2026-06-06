"""Unit tests for flexpipe.ingest.pathoplexus — HTTP-mock tests via `responses`."""

import pytest
import responses as resp_lib

from flexpipe.ingest.pathoplexus import (
    base_params,
    build_url,
    fetch_metadata,
    fetch_sequences,
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


class TestFetchMetadata:
    _URL = "https://lapis.test/YFV/sample/details"

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
    def test_http_error_raises(self):
        import requests

        resp_lib.add(resp_lib.GET, self._URL, status=500)
        with pytest.raises(requests.HTTPError):
            fetch_metadata(self._URL)


class TestFetchSequences:
    _URL = "https://lapis.test/YFV/sample/unalignedNucleotideSequences"

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
