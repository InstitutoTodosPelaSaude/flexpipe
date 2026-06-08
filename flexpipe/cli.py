"""
Console-script entry points for flexpipe.

Each function here is registered as a ``[project.scripts]`` entry point in
``pyproject.toml``.  Every entry point delegates directly to the corresponding
``flexpipe.*`` module's ``main()`` function.

The orchestrator entry point ``run`` (``flexpipe-run``) calls ``flexpipe.run.main``.
"""

# ── Per-rule entry points ─────────────────────────────────────────────────────


def fetch_pathoplexus() -> None:
    """flexpipe-fetch-pathoplexus — fetch from Pathoplexus/LAPIS."""
    from flexpipe.ingest.pathoplexus import main

    main()


def fetch_ncbi() -> None:
    """flexpipe-fetch-ncbi — fetch from NCBI Entrez."""
    from flexpipe.ingest.ncbi import main

    main()


def merge() -> None:
    """flexpipe-merge — merge remote data with local sequences."""
    from flexpipe.ingest.merge import main

    main()


def curate() -> None:
    """flexpipe-curate — ViralQC join, region, clade_truncated, dedup."""
    from flexpipe.curate.pipeline import main

    main()


def qc_summary() -> None:
    """flexpipe-qc-summary — build per-run QC report from ingest curation outputs."""
    from flexpipe.curate.qc_summary import main

    main()


def coordinates() -> None:
    """flexpipe-coordinates — geocode locations via Nominatim."""
    from flexpipe.geo.coordinates import main

    main()


def disambiguate_geo() -> None:
    """flexpipe-disambiguate-geo — make ambiguous geographic display names unique."""
    from flexpipe.geo.coordinates import main_disambiguate

    main_disambiguate()


def update_cache() -> None:
    """flexpipe-update-cache — merge new coordinates into the workdir cache.

    Args (from sys.argv):
        --new-latlongs  Path to the freshly generated latlongs.tsv
        --cache         Path to the persistent cache TSV (workdir/cache/)
        --output        Path to write the updated cache (same as --cache for in-place)
    """
    import argparse

    from flexpipe.geo.cache import merge_coordinate_cache

    parser = argparse.ArgumentParser(
        description="Merge newly geocoded coordinates into the persistent workdir cache."
    )
    parser.add_argument(
        "--new-latlongs", required=True, help="Path to freshly generated latlongs.tsv"
    )
    parser.add_argument("--cache", required=True, help="Path to existing cache TSV")
    parser.add_argument("--output", required=True, help="Path to write updated cache TSV")
    args = parser.parse_args()
    merge_coordinate_cache(args.new_latlongs, args.cache, args.output)


def name2hue() -> None:
    """flexpipe-name2hue — generate hue mapping from subsampled metadata."""
    from flexpipe.colors.hues import main

    main()


def colours() -> None:
    """flexpipe-colours — assign hex colours per metadata value."""
    from flexpipe.colors.scheme import main

    main()


def collapse_traits() -> None:
    """flexpipe-collapse-traits — cap trait states before TreeTime inference."""
    from flexpipe.phylo.traits import main

    main()


def normalize_dates() -> None:
    """flexpipe-normalize-dates — normalize flexible metadata date strings."""
    from flexpipe.curate.dates import main

    main()


def reference_mask() -> None:
    """flexpipe-reference-mask — generate BED masks from reference annotations."""
    from flexpipe.phylo.reference_mask import main

    main()


def validate_build() -> None:
    """flexpipe-validate-build — validate a build config.yaml before running."""
    from flexpipe.validate import main

    main()


# ── Orchestrator ─────────────────────────────────────────────────────────────


def run() -> None:
    """flexpipe-run — run the full pipeline for one build end-to-end."""
    from flexpipe.run import main

    main()
