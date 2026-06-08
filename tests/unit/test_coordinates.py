"""Unit tests for flexpipe.geo.coordinates — query building and cache loading."""

from unittest.mock import MagicMock, patch

import pandas as pd

from flexpipe.geo.coordinates import (
    build_queries,
    disambiguate_geographic_values,
    find_coordinates,
    geocode_metadata,
    load_cache,
    load_cache_by_query,
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


class TestDisambiguateGeographicValues:
    def test_duplicate_city_names_get_unique_parent_suffix(self):
        df = pd.DataFrame(
            [
                {
                    "country": "United States",
                    "division": "Illinois",
                    "location": "Springfield",
                },
                {
                    "country": "United States",
                    "division": "Massachusetts",
                    "location": "Springfield",
                },
            ]
        )
        out = disambiguate_geographic_values(df, ["country", "division", "location"])
        assert out["location"].tolist() == [
            "Springfield, Illinois",
            "Springfield, Massachusetts",
        ]

    def test_unique_city_name_is_unchanged(self):
        df = pd.DataFrame([{"country": "Brazil", "division": "Sao Paulo", "location": "Campinas"}])
        out = disambiguate_geographic_values(df, ["country", "division", "location"])
        assert out["location"].iloc[0] == "Campinas"


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

    def test_loads_v2_cache_by_query(self, tmp_path):
        f = tmp_path / "cache.tsv"
        f.write_text(
            "level\tname\tquery\tlatitude\tlongitude\n"
            "location\tSpringfield, Illinois\tUnited States, Illinois, Springfield\t39.78\t-89.64\n"
            "location\tSpringfield, Massachusetts\tUnited States, Massachusetts, Springfield\t42.10\t-72.59\n",
            encoding="utf-8",
        )
        cache = load_cache_by_query(str(f), ["location"])
        assert cache["location"]["United States, Illinois, Springfield"] == ("39.78", "-89.64")
        assert cache["location"]["United States, Massachusetts, Springfield"] == (
            "42.10",
            "-72.59",
        )


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


class TestGeocodeMetadata:
    def test_duplicate_city_names_write_distinct_cache_queries(self, tmp_path):
        df = pd.DataFrame(
            [
                {
                    "country": "United States",
                    "division": "Illinois",
                    "location": "Springfield",
                },
                {
                    "country": "United States",
                    "division": "Massachusetts",
                    "location": "Springfield",
                },
            ]
        )
        output = tmp_path / "latlongs.tsv"
        cache = tmp_path / "cache.tsv"

        def fake_find(query, level, geolocator):
            if level == "location" and "Illinois" in query:
                return ("39.78", "-89.64")
            if level == "location" and "Massachusetts" in query:
                return ("42.10", "-72.59")
            return ("0", "0")

        with (
            patch("flexpipe.geo.coordinates._make_geolocator", return_value=MagicMock()),
            patch("flexpipe.geo.coordinates.find_coordinates", side_effect=fake_find),
        ):
            geocode_metadata(
                df,
                ["country", "division", "location"],
                cache_path="",
                output_path=str(output),
                workdir_cache_path=str(cache),
            )

        latlongs = output.read_text()
        assert "location\tSpringfield, Illinois\t39.78\t-89.64" in latlongs
        assert "location\tSpringfield, Massachusetts\t42.10\t-72.59" in latlongs
        cache_rows = cache.read_text()
        assert "United States, Illinois, Springfield, Illinois" in cache_rows
        assert "United States, Massachusetts, Springfield, Massachusetts" in cache_rows
