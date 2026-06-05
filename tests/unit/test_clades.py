"""Unit tests for flexpipe.curate.clades.truncate_clade."""

import pytest

from flexpipe.curate.clades import truncate_clade


class TestTruncateClade:
    """Tests for ``truncate_clade``."""

    def test_basic_two_levels(self):
        assert truncate_clade("A.B.C.D", 2) == "A.B"

    def test_basic_one_level(self):
        assert truncate_clade("A.B.C.D", 1) == "A"

    def test_single_component_kept(self):
        """A clade with fewer parts than levels keeps all parts."""
        assert truncate_clade("I", 1) == "I"

    def test_fewer_parts_than_levels(self):
        """When fewer parts exist than requested, keep all."""
        assert truncate_clade("A", 3) == "A"

    def test_exactly_n_levels(self):
        assert truncate_clade("A.B", 2) == "A.B"

    def test_empty_string(self):
        assert truncate_clade("", 1) == ""

    def test_whitespace_only(self):
        assert truncate_clade("   ", 2) == ""

    def test_none_like_nan(self):
        """Falsy NaN string from pandas fillna should return empty."""
        assert truncate_clade("nan", 1) == "nan"  # treated as literal

    def test_custom_separator(self):
        assert truncate_clade("A/B/C", 2, sep="/") == "A/B"

    def test_leading_trailing_separator(self):
        """Parts are filtered empty, so leading/trailing seps don't create empty levels."""
        assert truncate_clade(".A.B.", 2) == "A.B"

    def test_nested_yfv_clade(self):
        """Realistic YFV genotype (clade_levels=1 produces top-level only)."""
        assert truncate_clade("I.A.1", 1) == "I"
        assert truncate_clade("I.A.1", 2) == "I.A"

    def test_integer_levels_zero(self):
        """Requesting 0 levels returns empty string (no parts kept)."""
        assert truncate_clade("A.B.C", 0) == ""
