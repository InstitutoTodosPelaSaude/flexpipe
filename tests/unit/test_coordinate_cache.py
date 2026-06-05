"""Unit tests for flexpipe.geo.cache.merge_coordinate_cache.

These are regression tests for the destructive-cache bug that existed in the
original inline ``python3 -c`` Snakefile block: if the cache was not properly
deduplicated the merge would produce a cache larger than intended, or wipe out
manually edited entries.
"""

import pytest
import pandas as pd

from flexpipe.geo.cache import merge_coordinate_cache, _read_cache


def _write_cache(path, rows):
    """Write a minimal cache TSV to *path*."""
    df = pd.DataFrame(rows, columns=["level", "name", "latitude", "longitude"])
    df.to_csv(path, sep="\t", index=False)
    return path


class TestReadCache:
    """Tests for the private ``_read_cache`` helper."""

    def test_missing_file_returns_empty_df(self, tmp_path):
        result = _read_cache(tmp_path / "nonexistent.tsv")
        assert len(result) == 0
        assert list(result.columns) == ["level", "name", "latitude", "longitude"]

    def test_reads_tsv_with_header_correctly(self, tmp_path):
        p = tmp_path / "cache.tsv"
        _write_cache(p, [
            ("division", "São Paulo", "-23.5", "-46.6"),
            ("country", "Brazil", "-14.2", "-51.9"),
        ])
        result = _read_cache(p)
        assert len(result) == 2
        assert result["name"].tolist() == ["São Paulo", "Brazil"]

    def test_reads_headerless_tsv(self, tmp_path):
        """Legacy format (old Snakefile inline block or latlongs.tsv) — no header row."""
        p = tmp_path / "legacy.tsv"
        p.write_text(
            "division\tSão Paulo\t-23.5\t-46.6\n"
            "country\tBrazil\t-14.2\t-51.9\n",
            encoding="utf-8",
        )
        result = _read_cache(p)
        assert len(result) == 2
        names = set(result["name"])
        assert "São Paulo" in names
        assert "Brazil" in names

    def test_headerless_with_blank_lines(self, tmp_path):
        """latlongs.tsv format: blank lines separate trait groups."""
        p = tmp_path / "latlongs.tsv"
        p.write_text(
            "division\tSão Paulo\t-23.5\t-46.6\n"
            "division\tMinas Gerais\t-18.5\t-44.1\n"
            "\n"
            "location\tCampinas\t-22.9\t-47.0\n",
            encoding="utf-8",
        )
        result = _read_cache(p)
        assert len(result) == 3
        assert "" not in result["name"].tolist()

    def test_merge_from_legacy_latlongs(self, tmp_path):
        """merge_coordinate_cache correctly reads headerless latlongs.tsv as input."""
        new = tmp_path / "latlongs.tsv"
        cache = tmp_path / "cache.tsv"
        output = tmp_path / "output.tsv"

        # latlongs.tsv format — no header, blank lines between groups
        new.write_text(
            "division\tParaná\t-24.8\t-51.0\n"
            "\n"
            "location\tCuritiba\t-25.4\t-49.2\n",
            encoding="utf-8",
        )
        # existing cache with header (new format)
        _write_cache(cache, [("country", "Brazil", "-14.2", "-51.9")])

        merge_coordinate_cache(new, cache, output)

        result = pd.read_csv(output, sep="\t")
        names = set(result["name"])
        assert "Paraná" in names
        assert "Curitiba" in names
        assert "Brazil" in names


class TestMergeCoordinateCache:
    """Tests for ``merge_coordinate_cache``."""

    def test_merge_new_into_nonexistent_cache(self, tmp_path):
        new = tmp_path / "latlongs.tsv"
        cache = tmp_path / "cache.tsv"  # does not exist
        output = tmp_path / "output.tsv"

        _write_cache(new, [("division", "Rio de Janeiro", "-22.9", "-43.2")])
        merge_coordinate_cache(new, cache, output)

        result = pd.read_csv(output, sep="\t")
        assert len(result) == 1
        assert result["name"].tolist() == ["Rio de Janeiro"]

    def test_existing_cache_entries_preserved(self, tmp_path):
        new = tmp_path / "latlongs.tsv"
        cache = tmp_path / "cache.tsv"
        output = tmp_path / "output.tsv"

        _write_cache(cache, [("country", "Brazil", "-14.2", "-51.9")])
        _write_cache(new, [("division", "Amazonas", "-3.1", "-60.0")])

        merge_coordinate_cache(new, cache, output)

        result = pd.read_csv(output, sep="\t")
        names = set(result["name"])
        assert "Brazil" in names
        assert "Amazonas" in names

    def test_cache_wins_on_duplicate_key(self, tmp_path):
        """If the same (level, name) appears in both cache and new file, cache wins."""
        new = tmp_path / "latlongs.tsv"
        cache = tmp_path / "cache.tsv"
        output = tmp_path / "output.tsv"

        # Cache has a manual (corrected) entry for São Paulo
        _write_cache(cache, [("division", "São Paulo", "-23.5", "-46.6")])
        # New file has a Nominatim result that may differ slightly
        _write_cache(new, [("division", "São Paulo", "-23.55", "-46.63")])

        merge_coordinate_cache(new, cache, output)

        result = pd.read_csv(output, sep="\t", dtype=str)
        sp_rows = result[result["name"] == "São Paulo"]
        assert len(sp_rows) == 1
        # The cache (original) value should win
        assert sp_rows["latitude"].iloc[0] == "-23.5"

    def test_no_duplicate_rows_produced(self, tmp_path):
        """Merging the same file twice must not produce duplicate rows."""
        data = [
            ("division", "Bahia", "-12.0", "-41.7"),
            ("country", "Brazil", "-14.2", "-51.9"),
        ]
        new = tmp_path / "latlongs.tsv"
        cache = tmp_path / "cache.tsv"
        output = tmp_path / "output.tsv"

        _write_cache(new, data)
        _write_cache(cache, data)

        merge_coordinate_cache(new, cache, output)

        result = pd.read_csv(output, sep="\t")
        assert len(result) == 2  # no duplicates

    def test_creates_parent_directory(self, tmp_path):
        """Output path in a subdirectory that does not exist yet must be created."""
        new = tmp_path / "latlongs.tsv"
        cache = tmp_path / "cache.tsv"
        output = tmp_path / "subdir" / "nested" / "output.tsv"

        _write_cache(new, [("country", "Brazil", "-14.2", "-51.9")])

        merge_coordinate_cache(new, cache, output)
        assert output.exists()

    def test_in_place_update(self, tmp_path):
        """Output path == cache path should safely update the cache in-place."""
        cache = tmp_path / "cache.tsv"
        new = tmp_path / "latlongs.tsv"

        _write_cache(cache, [("country", "Brazil", "-14.2", "-51.9")])
        _write_cache(new, [("division", "Pará", "-1.5", "-52.0")])

        merge_coordinate_cache(new, cache, cache)  # output == cache

        result = pd.read_csv(cache, sep="\t")
        assert len(result) == 2
