"""Unit tests for flexpipe.config.resolve_subsample_config."""

import copy

from flexpipe.config import resolve_subsample_config


class TestResolveSubsampleConfig:
    """resolve_subsample_config — max_date injection logic."""

    def _base_config(self):
        return {
            "defaults": {"min_date": 2015, "exclude": "builds/yfv-brazil/ignore.txt"},
            "samples": {
                "brazil": {
                    "query": "country == 'Brazil'",
                    "group_by": ["division", "year"],
                    "sequences_per_group": 100,
                }
            },
        }

    # --- run_date provided -------------------------------------------------------

    def test_injects_max_date_into_defaults(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, "2026-01-01")
        assert result["defaults"]["max_date"] == "2026-01-01"

    def test_preserves_existing_defaults_keys(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, "2026-01-01")
        assert result["defaults"]["min_date"] == 2015
        assert result["defaults"]["exclude"] == "builds/yfv-brazil/ignore.txt"

    def test_preserves_samples_section_unchanged(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, "2026-01-01")
        assert result["samples"] == raw["samples"]

    def test_does_not_mutate_input(self):
        raw = self._base_config()
        original = copy.deepcopy(raw)
        resolve_subsample_config(raw, "2026-01-01")
        assert raw == original

    def test_creates_defaults_section_if_absent(self):
        raw = {"samples": {"all": {"sequences_per_group": 50}}}
        result = resolve_subsample_config(raw, "2025-06-01")
        assert result["defaults"]["max_date"] == "2025-06-01"

    def test_overwrites_existing_max_date(self):
        raw = self._base_config()
        raw["defaults"]["max_date"] = "2020-01-01"
        result = resolve_subsample_config(raw, "2026-03-15")
        assert result["defaults"]["max_date"] == "2026-03-15"

    def test_returns_deep_copy(self):
        """Mutating the result must not affect the original."""
        raw = self._base_config()
        result = resolve_subsample_config(raw, "2026-01-01")
        result["defaults"]["max_date"] = "MUTATED"
        assert "max_date" not in raw["defaults"]

    # --- run_date absent / empty ------------------------------------------------

    def test_no_max_date_when_run_date_is_none(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, None)
        assert "max_date" not in result.get("defaults", {})

    def test_no_max_date_when_run_date_is_empty_string(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, "")
        assert "max_date" not in result.get("defaults", {})

    def test_returns_same_structure_when_no_run_date(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, "")
        assert result == raw

    def test_no_mutation_when_no_run_date(self):
        raw = self._base_config()
        original = copy.deepcopy(raw)
        resolve_subsample_config(raw, None)
        assert raw == original


class TestResolveSubsampleConfigBackbone:
    """resolve_subsample_config — backbone_strains injection."""

    def _base_config(self):
        return {
            "defaults": {"min_date": 2015},
            "samples": {
                "focal": {
                    "query": "country == 'Brazil'",
                    "group_by": ["division", "year"],
                    "sequences_per_group": 10,
                }
            },
        }

    # --- backbone_strains provided -----------------------------------------------

    def test_injects_backbone_sample_set(self):
        raw = self._base_config()
        result = resolve_subsample_config(
            raw, None, backbone_strains="/tmp/cfg/backbone_strains.txt"
        )
        assert "__backbone__" in result["samples"]
        assert result["samples"]["__backbone__"] == {"include": "/tmp/cfg/backbone_strains.txt"}

    def test_backbone_does_not_affect_existing_samples(self):
        raw = self._base_config()
        result = resolve_subsample_config(
            raw, None, backbone_strains="/tmp/cfg/backbone_strains.txt"
        )
        assert "focal" in result["samples"]
        assert result["samples"]["focal"] == raw["samples"]["focal"]

    def test_backbone_and_run_date_together(self):
        raw = self._base_config()
        result = resolve_subsample_config(
            raw, "2026-06-01", backbone_strains="/tmp/cfg/backbone_strains.txt"
        )
        assert result["defaults"]["max_date"] == "2026-06-01"
        assert "__backbone__" in result["samples"]

    def test_backbone_creates_samples_section_if_absent(self):
        raw = {"defaults": {"min_date": 2020}}
        result = resolve_subsample_config(raw, None, backbone_strains="/tmp/strains.txt")
        assert "__backbone__" in result["samples"]

    def test_backbone_does_not_mutate_input(self):
        raw = self._base_config()
        original = copy.deepcopy(raw)
        resolve_subsample_config(raw, None, backbone_strains="/tmp/strains.txt")
        assert raw == original

    # --- backbone_strains absent / None / empty ----------------------------------

    def test_no_backbone_when_none(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, None, backbone_strains=None)
        assert "__backbone__" not in result.get("samples", {})

    def test_no_backbone_when_empty_string(self):
        raw = self._base_config()
        result = resolve_subsample_config(raw, None, backbone_strains="")
        assert "__backbone__" not in result.get("samples", {})

    def test_two_arg_call_unchanged(self):
        """Existing callers that only pass raw + run_date are unaffected."""
        raw = self._base_config()
        result = resolve_subsample_config(raw, "2026-01-01")
        assert "__backbone__" not in result.get("samples", {})
        assert result["defaults"]["max_date"] == "2026-01-01"
