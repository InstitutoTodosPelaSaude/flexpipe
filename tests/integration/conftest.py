"""Shared helpers for flexpipe integration tests.

These functions are used by test_ingest_wiring.py and test_phylo_wiring.py
to automatically discover all build scaffolds without maintaining duplicated
hardcoded lists.  New builds are picked up the moment ``builds/<name>/config.yaml``
exists.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def all_build_configs() -> list[Path]:
    """Return all ``builds/*/config.yaml`` paths, sorted by build name.

    This replaces the previously hardcoded ``BUILD_CONFIGS`` list in the
    integration test files.  Any new build directory is automatically included
    in ``test_all_scaffold_builds_dry_run`` / ``test_all_scaffold_phylo_dry_run``
    without editing these files.
    """
    return sorted((REPO_ROOT / "builds").glob("*/config.yaml"))


def real_reference_builds() -> list[Path]:
    """Return build configs whose ``reference.gb`` does not contain ``PLACEHOLDER``.

    Phylo dry-runs are skipped for builds with placeholder references because
    a real reference is required for alignment, masking, and tree building.
    """
    result = []
    for config_path in all_build_configs():
        ref = config_path.parent / "reference.gb"
        if ref.exists() and "PLACEHOLDER" not in ref.read_text():
            result.append(config_path)
    return result
