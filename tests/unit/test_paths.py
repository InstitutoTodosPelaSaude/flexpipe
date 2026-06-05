"""Unit tests for flexpipe.paths.WorkdirPaths.

These tests verify the service-readiness requirement: all output paths are
anchored in the workdir, not the source tree.
"""

import pytest
from pathlib import Path

from flexpipe.paths import WorkdirPaths


@pytest.fixture
def workdir(tmp_path) -> Path:
    """A temporary workdir root."""
    return tmp_path / "run_workdir"


@pytest.fixture
def paths(workdir) -> WorkdirPaths:
    return WorkdirPaths.from_root(workdir)


class TestWorkdirPathsProperties:
    """All properties must be sub-paths of root."""

    def test_root_is_absolute(self, paths, workdir):
        assert paths.root.is_absolute()

    def test_results_under_root(self, paths):
        assert paths.results.parts[:len(paths.root.parts)] == paths.root.parts

    def test_ingest_dir_under_results(self, paths):
        assert str(paths.ingest_dir).startswith(str(paths.results))

    def test_subsampled_dir_under_results(self, paths):
        assert str(paths.subsampled_dir).startswith(str(paths.results))

    def test_subsampled_metadata_filename(self, paths):
        assert paths.subsampled_metadata.name == "metadata.tsv"

    def test_subsampled_sequences_filename(self, paths):
        assert paths.subsampled_sequences.name == "sequences.fasta"

    def test_auspice_json_filename(self, paths):
        assert paths.auspice_json.name == "results.json"

    def test_cache_coordinates_path(self, paths):
        assert paths.cache_coordinates.name == "cache_coordinates.tsv"
        assert str(paths.cache_coordinates).startswith(str(paths.root))

    def test_latlongs_under_generated_config(self, paths):
        assert str(paths.latlongs).startswith(str(paths.generated_config_dir))

    def test_colour_scheme_under_generated_config(self, paths):
        assert str(paths.colour_scheme).startswith(str(paths.generated_config_dir))

    def test_name2hue_under_generated_config(self, paths):
        assert str(paths.name2hue).startswith(str(paths.generated_config_dir))

    def test_manifest_directly_under_root(self, paths):
        assert paths.manifest.parent == paths.root

    def test_ingest_log_under_logs(self, paths):
        assert str(paths.ingest_log).startswith(str(paths.logs_dir))

    def test_phylo_log_under_logs(self, paths):
        assert str(paths.phylo_log).startswith(str(paths.logs_dir))


class TestWorkdirPathsEnsureDirs:
    """ensure_dirs() creates all directories idempotently."""

    def test_creates_directories(self, paths):
        paths.ensure_dirs()
        assert paths.ingest_dir.is_dir()
        assert paths.subsampled_dir.is_dir()
        assert paths.alignments_dir.is_dir()
        assert paths.auspice_dir.is_dir()
        assert paths.generated_config_dir.is_dir()
        assert paths.cache_dir.is_dir()
        assert paths.logs_dir.is_dir()

    def test_idempotent(self, paths):
        paths.ensure_dirs()
        paths.ensure_dirs()  # must not raise

    def test_source_tree_untouched(self, paths, tmp_path):
        """No files/directories should be created outside the workdir root."""
        source_tree = tmp_path / "source_tree"
        source_tree.mkdir()
        paths.ensure_dirs()
        # Verify the source tree is empty
        created_outside = [
            p for p in source_tree.rglob("*") if p.is_dir()
        ]
        assert created_outside == []


class TestWorkdirPathsFromRoot:
    """WorkdirPaths.from_root() factory."""

    def test_string_path_accepted(self, tmp_path):
        paths = WorkdirPaths.from_root(str(tmp_path))
        assert paths.root == tmp_path.resolve()

    def test_path_object_accepted(self, tmp_path):
        paths = WorkdirPaths.from_root(tmp_path)
        assert paths.root == tmp_path.resolve()

    def test_resolves_to_absolute(self):
        paths = WorkdirPaths.from_root(".")
        assert paths.root.is_absolute()
