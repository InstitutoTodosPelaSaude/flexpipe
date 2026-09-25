"""Unit tests for flexpipe.data.load_data_yaml override and merge semantics."""

import pytest
import yaml

from flexpipe.curate.viralqc_aliases import labels_match_expected, load_alias_registry
from flexpipe.data import _deep_merge, load_data_yaml

PACKAGE = "flexpipe.data.viralqc"
FILENAME = "aliases.yaml"


class TestDeepMerge:
    def test_nested_mappings_merge_key_by_key(self):
        base = {"viruses": {"a": {"aliases": ["x"]}, "b": {"aliases": ["y"]}}}
        over = {"viruses": {"c": {"aliases": ["z"]}}}
        assert _deep_merge(base, over) == {
            "viruses": {
                "a": {"aliases": ["x"]},
                "b": {"aliases": ["y"]},
                "c": {"aliases": ["z"]},
            }
        }

    def test_lists_are_replaced_not_concatenated(self):
        assert _deep_merge({"k": [1, 2]}, {"k": [3]}) == {"k": [3]}

    def test_override_wins_on_scalars(self):
        assert _deep_merge({"k": 1}, {"k": 2}) == {"k": 2}


class TestLoadDataYamlOverride:
    def _write(self, tmp_path, payload):
        p = tmp_path / "custom.yaml"
        p.write_text(yaml.safe_dump(payload), encoding="utf-8")
        return p

    def test_without_merge_the_override_replaces_the_bundle(self, tmp_path):
        p = self._write(tmp_path, {"viruses": {"my_virus": {"aliases": ["mine"]}}})
        data = load_data_yaml(PACKAGE, FILENAME, override=str(p))
        assert set(data["viruses"]) == {"my_virus"}

    def test_with_merge_the_bundled_entries_survive(self, tmp_path):
        p = self._write(tmp_path, {"viruses": {"my_virus": {"aliases": ["mine"]}}})
        data = load_data_yaml(PACKAGE, FILENAME, override=str(p), merge=True)
        assert "my_virus" in data["viruses"]
        assert "flu_b" in data["viruses"]

    def test_merge_still_lets_an_override_redefine_one_entry(self, tmp_path):
        p = self._write(tmp_path, {"viruses": {"flu_b": {"aliases": ["only_this"]}}})
        data = load_data_yaml(PACKAGE, FILENAME, override=str(p), merge=True)
        assert data["viruses"]["flu_b"]["aliases"] == ["only_this"]
        assert "measles" in data["viruses"]

    def test_missing_override_still_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_data_yaml(PACKAGE, FILENAME, override=str(tmp_path / "nope.yaml"), merge=True)


class TestAliasRegistryMerges:
    def test_adding_one_virus_keeps_the_bundled_ones(self, tmp_path):
        p = tmp_path / "aliases.yaml"
        p.write_text(
            yaml.safe_dump({"viruses": {"flu_c": {"aliases": ["Influenza C virus"]}}}),
            encoding="utf-8",
        )
        # the registry cache is keyed by override path, and tmp_path is unique per test
        registry = load_alias_registry(str(p))
        assert "flu_c" in registry["viruses"]
        assert "measles" in registry["viruses"]
        assert labels_match_expected("Influenza C virus", "flu_c", "viruses", aliases_file=str(p))
