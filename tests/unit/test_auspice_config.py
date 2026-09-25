"""Unit tests for flexpipe.phylo.auspice_config.resolve_auspice_config."""

from flexpipe.phylo.auspice_config import resolve_auspice_config

RAW = {
    "title": "Test",
    "colorings": [
        {"key": "clade", "type": "categorical"},
        {"key": "num_date", "title": "Date", "type": "continuous"},
        {"key": "country", "type": "categorical"},
    ],
    "filters": ["country", "num_date", "clade"],
    "display_defaults": {"color_by": "country", "distance_measure": "num_date"},
    "panels": ["tree", "map", "entropy"],
}


class TestWithTimetree:
    def test_config_is_returned_unchanged(self):
        assert resolve_auspice_config(RAW, timetree=True) == RAW

    def test_default_keeps_the_time_scale(self):
        assert resolve_auspice_config(RAW) == RAW

    def test_the_input_is_not_mutated(self):
        resolve_auspice_config(RAW, timetree=False)
        assert RAW["display_defaults"]["distance_measure"] == "num_date"
        assert len(RAW["colorings"]) == 3


class TestWithoutTimetree:
    def test_distance_measure_falls_back_to_divergence(self):
        out = resolve_auspice_config(RAW, timetree=False)
        assert out["display_defaults"]["distance_measure"] == "div"

    def test_date_coloring_is_dropped(self):
        out = resolve_auspice_config(RAW, timetree=False)
        assert [c["key"] for c in out["colorings"]] == ["clade", "country"]

    def test_date_filter_is_dropped(self):
        out = resolve_auspice_config(RAW, timetree=False)
        assert out["filters"] == ["country", "clade"]

    def test_panels_are_left_to_the_build(self):
        out = resolve_auspice_config(RAW, timetree=False)
        assert out["panels"] == ["tree", "map", "entropy"]

    def test_config_without_the_optional_sections_is_accepted(self):
        out = resolve_auspice_config({"title": "Bare"}, timetree=False)
        assert out == {"title": "Bare"}

    def test_string_colorings_are_handled(self):
        out = resolve_auspice_config(
            {"colorings": ["clade", "num_date"]}, timetree=False
        )
        assert out["colorings"] == ["clade"]
