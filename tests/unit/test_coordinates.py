"""Unit tests for flexpipe.geo.coordinates — query building and cache loading."""

from unittest.mock import MagicMock, patch

import pandas as pd

from flexpipe.geo.coordinates import (
    build_queries,
    find_coordinates,
    load_cache,
    write_output,
)


class TestBuildQueries:
    def _df(self, rows):
        return pd.DataFrame(rows)

    def test_single_column_single_row(self):
        df = self._df([{"country": "Brazil"}])
        qs = build_queries(df, ["country"])
        assert len(qs) == 1
        assert qs[0] == ("country", ["Brazil"])

    def test_two_columns_build_nested_queries(self):
        df = self._df([{"country": "Brazil", "division": "Amazonas"}])
        qs = build_queries(df, ["country", "division"])
        assert ("country", ["Brazil"]) in qs
        assert ("division", ["Brazil", "Amazonas"]) in qs

    def test_deduplication(self):
        df = self._df(
            [
                {"country": "Brazil", "division": "Amazonas"},
                {"country": "Brazil", "division": "Amazonas"},
            ]
        )
        qs = build_queries(df, ["country", "division"])
        unique_keys = [(q[0], tuple(q[1])) for q in qs]
        assert len(unique_keys) == len(set(unique_keys))

    def test_region_column_excluded(self):
        df = self._df([{"country": "Brazil", "region": "South America"}])
        qs = build_queries(df, ["country", "region"])
        levels = [q[0] for q in qs]
        assert "region" not in levels

    def test_empty_columns_returns_empty(self):
        df = self._df([{"region": "South America"}])
        qs = build_queries(df, ["region"])
        assert qs == []


class TestLoadCache:
    def test_loads_existing_cache(self, tmp_path):
        f = tmp_path / "cache.tsv"
        f.write_text("country\tBrazil\t-14.235\t-51.925\n\n", encoding="utf-8")
        cache = load_cache(str(f), ["country"])
        assert cache["country"]["Brazil"] == ("-14.235", "-51.925")

    def test_missing_file_returns_empty_dict(self, tmp_path):
        cache = load_cache(str(tmp_path / "nonexistent.tsv"), ["country"])
        assert cache == {"country": {}}

    def test_ignores_columns_not_in_list(self, tmp_path):
        f = tmp_path / "cache.tsv"
        f.write_text("division\tAmazonas\t-3.4\t-65.2\n\n", encoding="utf-8")
        cache = load_cache(str(f), ["country"])
        assert "division" not in cache
        assert cache == {"country": {}}


class TestWriteOutput:
    def test_basic_output(self, tmp_path):
        out = str(tmp_path / "out.tsv")
        results = {"country": {"Brazil": ("-14.235", "-51.925")}}
        write_output(results, out)
        content = open(out).read()
        assert "country\tBrazil\t-14.235\t-51.925" in content

    def test_force_override_applied(self, tmp_path):
        out = str(tmp_path / "out.tsv")
        results = {"country": {"Brazil": ("0", "0")}}
        write_output(results, out, force_coordinates={"Brazil": ("-14.235", "-51.925")})
        content = open(out).read()
        assert "-14.235" in content
        assert "\t0\t" not in content


class TestFindCoordinates:
    def test_successful_geocode(self):
        mock_loc = MagicMock()
        mock_loc.latitude = -14.235
        mock_loc.longitude = -51.925
        geolocator = MagicMock()
        geolocator.geocode.return_value = mock_loc

        with patch("flexpipe.geo.coordinates.time.sleep"):
            lat, lon = find_coordinates("Brazil", "country", geolocator)

        assert lat == "-14.235"
        assert lon == "-51.925"

    def test_not_found_returns_na(self):
        geolocator = MagicMock()
        geolocator.geocode.return_value = None

        with patch("flexpipe.geo.coordinates.time.sleep"):
            lat, lon = find_coordinates("Nonexistent Place XYZ", "country", geolocator)

        assert lat == "NA"
        assert lon == "NA"
