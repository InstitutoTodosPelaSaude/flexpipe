"""Pre-run build configuration validator (``flexpipe-validate-build``).

Loads the build ``config.yaml`` with ``skip_viralqc=True``, runs pydantic
validation, then applies a set of checks that map to common live-run blockers
recorded in ``builds/GAPS_LOG.md`` and ``builds/MULTI_BUILD_LEARNINGS.md``.

Exit codes:
    0 — all checks passed (errors = 0)
    1 — one or more errors found

Warnings are printed but do not affect the exit code; they flag conditions that
are valid but may produce unexpected results (e.g. a QC skip, an NCBI email
inherited from the environment, header-only clades.tsv).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


# ── Formatted output helpers ──────────────────────────────────────────────────


def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠  {msg}")


def _err(msg: str) -> None:
    print(f"  ✗  {msg}")


# ── Individual checks ─────────────────────────────────────────────────────────


def _check_subsample_yaml(build_dir: Path, errors: list[str], warnings: list[str]) -> None:
    """Verify subsample.yaml uses supported augur subsample keys."""
    sub_path = build_dir / "subsample.yaml"
    if not sub_path.exists():
        errors.append("subsample.yaml not found")
        _err("subsample.yaml not found")
        return

    raw = yaml.safe_load(sub_path.read_text()) or {}

    # Must use 'samples:' not 'subsamples:'
    if "subsamples" in raw and "samples" not in raw:
        errors.append("subsample.yaml uses 'subsamples:' — rename to 'samples:'")
        _err("subsample.yaml uses 'subsamples:' — rename to 'samples:'")
    else:
        _ok("subsample.yaml uses 'samples:'")

    samples = raw.get("samples", {})
    for name, sample in (samples.items() if isinstance(samples, dict) else []):
        group_by = sample.get("group_by", [])
        if isinstance(group_by, str):
            errors.append(f"subsample.samples.{name}.group_by must be a list, not a string")
            _err(f"samples.{name}.group_by must be a list (got string {group_by!r})")
        else:
            _ok(f"samples.{name}.group_by is a list")

        query = sample.get("query", "")
        if query and '"' in str(query):
            warnings.append(
                f"subsample.samples.{name}.query contains double-quotes; "
                "prefer single-quote column values to avoid shell-quoting issues"
            )
            _warn(
                f"samples.{name}.query uses double-quotes — consider single-quotes "
                "to avoid shell issues"
            )


def _check_reference_gb(build_dir: Path, errors: list[str], warnings: list[str]) -> None:
    """Verify reference.gb exists and is not a PLACEHOLDER."""
    ref = build_dir / "reference.gb"
    if not ref.exists():
        errors.append("reference.gb not found")
        _err("reference.gb not found")
        return
    text = ref.read_text()
    if "PLACEHOLDER" in text:
        warnings.append("reference.gb contains PLACEHOLDER — phylo stage will not run correctly")
        _warn("reference.gb is a PLACEHOLDER — replace before running phylogenetics")
    else:
        _ok("reference.gb exists and is not a placeholder")


def _check_clades_tsv(build_dir: Path, errors: list[str], warnings: list[str]) -> None:
    """Flag header-only clades.tsv as informational."""
    clades = build_dir / "clades.tsv"
    if not clades.exists():
        errors.append("clades.tsv not found")
        _err("clades.tsv not found")
        return
    lines = [ln for ln in clades.read_text().splitlines() if ln.strip()]
    if len(lines) <= 1:
        warnings.append(
            "clades.tsv is header-only — augur clades will emit empty node data "
            "(OK for first-pass; add mutation rows for production clades)"
        )
        _warn("clades.tsv is header-only — no mutation-based branch labels defined")
    else:
        _ok(f"clades.tsv has {len(lines) - 1} clade definition row(s)")


def _check_mask_sites_file(
    config_raw: dict, build_dir: Path, errors: list[str], warnings: list[str]
) -> None:
    """Verify mask_sites_file exists and is non-empty when configured."""
    mask_path_str = str(config_raw.get("parameters", {}).get("mask_sites_file", "") or "").strip()
    if not mask_path_str:
        _ok("mask_sites_file not set (no BED masking)")
        return
    mask_path = Path(mask_path_str)
    if not mask_path.is_absolute():
        # Try to resolve relative to build dir
        candidate = (build_dir / mask_path).resolve()
        if candidate.exists():
            mask_path = candidate
    if not mask_path.exists():
        errors.append(f"mask_sites_file not found: {mask_path}")
        _err(f"mask_sites_file not found: {mask_path}")
        return
    if not mask_path.read_text().strip():
        warnings.append(
            f"mask_sites_file exists but is empty: {mask_path} — "
            "the phylo pipeline takes the copy (no-mask) branch"
        )
        _warn(f"mask_sites_file is empty: {mask_path} (no-mask branch will be used)")
    else:
        _ok(f"mask_sites_file exists and is non-empty: {mask_path.name}")


def _check_viralqc_aliases(config_raw: dict, errors: list[str], warnings: list[str]) -> None:
    """Verify viralqc.expected_virus / expected_segment are resolvable alias keys."""
    try:
        from flexpipe.curate.viralqc_aliases import load_alias_registry
    except ImportError:
        warnings.append("Could not import viralqc_aliases — alias check skipped")
        return

    vqc = config_raw.get("viralqc", {})
    mode = vqc.get("mode", "run")
    if mode in ("skip", "precomputed"):
        warnings.append(
            f"viralqc.mode='{mode}' bypasses BLAST/Nextclade QC — "
            "use only with pre-curated sequences"
        )
        _warn(f"viralqc.mode='{mode}' skips QC; ensure sequences are already " "quality-controlled")

    aliases_file = vqc.get("aliases_file") or None

    try:
        registry = load_alias_registry(aliases_file)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not load ViralQC alias registry: {exc} — alias check skipped")
        return

    for cfg_key, section in [
        ("expected_virus", "viruses"),
        ("expected_segment", "segments"),
    ]:
        value = str(vqc.get(cfg_key, "") or "").strip()
        if not value:
            _ok(f"viralqc.{cfg_key} not set (no cross-contamination filter)")
            continue
        # Check if value is a known registry key or alias.
        section_data = registry.get(section, {}) or {}
        known_keys = set(str(k) for k in section_data)
        known_aliases: set[str] = set()
        for entry_data in section_data.values():
            if isinstance(entry_data, dict):
                for alias in entry_data.get("aliases", []):
                    known_aliases.add(str(alias))
        if value in known_keys or value in known_aliases:
            _ok(f"viralqc.{cfg_key}={value!r} found in alias registry (OK)")
        else:
            # Literal matching still works downstream — issue a warning, not an error.
            warnings.append(
                f"viralqc.{cfg_key}={value!r} is not a named alias key in aliases.yaml; "
                f"literal matching will be used. Add it to aliases.yaml for alias-aware "
                f"contamination filtering."
            )
            _warn(
                f"viralqc.{cfg_key}={value!r} not in alias registry — "
                f"literal matching only (add to aliases.yaml for full alias support)"
            )


def _check_clade_filter(config_raw: dict, errors: list[str], warnings: list[str]) -> None:
    """Warn about likely-misconfigured clade_filter sections."""
    cf = config_raw.get("clade_filter", {}) or {}
    if not cf:
        return  # Section absent — pass-through by default; nothing to warn.

    column = str(cf.get("column", "") or "").strip()
    include = [str(v).strip() for v in cf.get("include", []) if str(v).strip()]
    exclude = [str(v).strip() for v in cf.get("exclude", []) if str(v).strip()]

    if column and not include and not exclude:
        warnings.append(
            "clade_filter.column is set but both include and exclude are empty; "
            "the filter will pass through all sequences (nothing filtered)."
        )
        _warn(
            "clade_filter.column set but include/exclude are both empty "
            "— filter will keep all sequences"
        )
    elif not column and (include or exclude):
        warnings.append(
            "clade_filter.include/exclude are set but column is empty; "
            "the filter is disabled and will pass through all sequences."
        )
        _warn("clade_filter.include/exclude set but column is empty — filter is disabled")
    elif column and (include or exclude):
        _ok(
            f"clade_filter: column={column!r}, include={include}, "
            f"exclude={exclude}, match={cf.get('match', 'exact')!r}"
        )


def _check_no_clade_source(config_raw: dict, errors: list[str], warnings: list[str]) -> None:
    """Error/warn when a skip-mode build uses clade-dependent config sections.

    viralqc.mode='skip' synthesizes no clade column — every sequence gets
    genome_quality='A' but clade/clade_truncated remain empty.  Any downstream
    config that depends on a populated clade column will silently fail:

    - qc.required_columns including 'clade' → augur filter drops ALL sequences.
    - traits.columns including 'clade' → augur traits infers an empty column.
    - clade_filter with column=clade/clade_truncated + include/exclude → filter is a no-op.
    """
    vqc = config_raw.get("viralqc", {}) or {}
    mode = vqc.get("mode", "run")
    if mode != "skip":
        return  # Only relevant for skip mode

    # ── required_columns: clade in skip mode → every row filtered → empty build ──
    qc = config_raw.get("qc", {}) or {}
    req_cols = [str(c) for c in (qc.get("required_columns") or [])]
    if "clade" in req_cols:
        msg = (
            "viralqc.mode='skip' produces no 'clade' column, but 'clade' is in "
            "qc.required_columns — augur filter will drop ALL sequences. "
            "Remove 'clade' from required_columns."
        )
        errors.append(msg)
        _err(msg)
    else:
        _ok("qc.required_columns does not include 'clade' (correct for skip mode)")

    # ── traits.columns: clade in skip mode → empty trait inference (warning) ──
    traits = config_raw.get("traits", {}) or {}
    trait_cols_raw = traits.get("columns", "") or ""
    if isinstance(trait_cols_raw, list):
        trait_cols = [str(c) for c in trait_cols_raw]
    else:
        trait_cols = str(trait_cols_raw).split()
    if "clade" in trait_cols:
        msg = (
            "viralqc.mode='skip' produces no 'clade' column, but 'clade' is in "
            "traits.columns — augur traits will infer an empty/absent trait column."
        )
        warnings.append(msg)
        _warn(
            "traits.columns includes 'clade' but skip mode has no clade — remove or leave for inertness"
        )

    # ── clade_filter: filtering on clade/clade_truncated in skip mode → no-op ──
    cf = config_raw.get("clade_filter", {}) or {}
    cf_column = str(cf.get("column", "") or "").strip()
    cf_include = [str(v).strip() for v in (cf.get("include") or []) if str(v).strip()]
    cf_exclude = [str(v).strip() for v in (cf.get("exclude") or []) if str(v).strip()]
    if cf_column in ("clade", "clade_truncated") and (cf_include or cf_exclude):
        msg = (
            f"viralqc.mode='skip' produces no '{cf_column}' column, but "
            f"clade_filter.column='{cf_column}' with include/exclude set — "
            "the filter will pass through all sequences (nothing filtered)."
        )
        warnings.append(msg)
        _warn(
            f"clade_filter.column='{cf_column}' but skip mode produces no clade "
            "— filter is a no-op (pass-through)"
        )


def _check_data_source_prerequisites(
    config_raw: dict, build_dir: Path, errors: list[str], warnings: list[str]
) -> None:
    """Check required fields for each data_source value."""
    data_source = config_raw.get("data_source", "pathoplexus")

    if data_source == "pathoplexus":
        organism = config_raw.get("pathoplexus", {}).get("organism", "")
        if not organism:
            errors.append("pathoplexus.organism is required when data_source='pathoplexus'")
            _err("pathoplexus.organism is not set")
        else:
            _ok(f"pathoplexus.organism={organism!r}")

    elif data_source == "ncbi":
        taxid = config_raw.get("ncbi", {}).get("taxid", 0)
        if not taxid:
            errors.append("ncbi.taxid is required when data_source='ncbi'")
            _err("ncbi.taxid is not set")
        else:
            _ok(f"ncbi.taxid={taxid}")

        ncbi_email = config_raw.get("ncbi", {}).get("email", "") or os.environ.get("NCBI_EMAIL", "")
        if not ncbi_email:
            errors.append("ncbi.email or NCBI_EMAIL env var is required when data_source='ncbi'")
            _err("ncbi.email not set and NCBI_EMAIL env var is absent")
        elif not config_raw.get("ncbi", {}).get("email"):
            warnings.append("ncbi.email is inherited from NCBI_EMAIL env var (not in config)")
            _warn("ncbi.email comes from NCBI_EMAIL env var — not reproducible from config alone")
        else:
            _ok("ncbi.email is set")

    elif data_source == "local":
        repo_root = build_dir.parent.parent  # builds/<name>/ → repo root
        for key in ["metadata", "sequences"]:
            path_str = str(config_raw.get("local", {}).get(key, "") or "").strip()
            if not path_str:
                errors.append(f"local.{key} is required when data_source='local'")
                _err(f"local.{key} is not set")
                continue
            path = Path(path_str)
            if path.is_absolute():
                resolved = path
            else:
                # Mirror config.py _resolve_path_value: try build_dir first, then repo root.
                build_candidate = (build_dir / path).resolve()
                repo_candidate = (repo_root / path).resolve()
                resolved = repo_candidate if repo_candidate.exists() else build_candidate
            if not resolved.exists():
                errors.append(f"local.{key} not found: {resolved}")
                _err(f"local.{key} not found: {resolved}")
            else:
                _ok(f"local.{key} exists: {resolved.name}")


def _check_cache_coordinates_header(
    config_raw: dict, build_dir: Path, errors: list[str], warnings: list[str]
) -> None:
    """Warn if cache_coordinates.tsv uses the old v1 header format."""
    cache_path_str = str(config_raw.get("files", {}).get("cache", "") or "").strip()
    if not cache_path_str:
        return  # No cache configured — nothing to check
    cache_path = Path(cache_path_str)
    if not cache_path.is_absolute():
        candidate = (build_dir / cache_path).resolve()
        if candidate.exists():
            cache_path = candidate
    if not cache_path.exists():
        return  # Optional file; existence already handled by config path resolution
    first_line = cache_path.read_text().split("\n", 1)[0].strip()
    v2_header_fields = {"level", "name", "query", "latitude", "longitude"}
    v1_header_fields = {"level", "query", "lat", "lon"}
    header_fields = set(first_line.split("\t")) | set(first_line.split(","))
    if v1_header_fields <= header_fields and not (v2_header_fields <= header_fields):
        warnings.append(
            "cache_coordinates.tsv appears to use the old v1 header "
            "(lat/lon instead of latitude/longitude); "
            "update to the v2 contract (level name query latitude longitude)"
        )
        _warn("cache_coordinates.tsv uses old v1 header — update to v2 (latitude/longitude)")
    else:
        _ok("cache_coordinates.tsv header looks like v2")


# ── Orchestrator ──────────────────────────────────────────────────────────────


def validate_build(config_path: str | Path) -> int:
    """Run all checks for a build config.yaml.

    Args:
        config_path: Path to the build ``config.yaml``.

    Returns:
        Exit code: ``0`` if no errors, ``1`` if one or more errors.
    """
    config_path = Path(config_path).resolve()
    build_dir = config_path.parent

    print(f"\nValidating: {config_path}\n")

    errors: list[str] = []
    warnings: list[str] = []

    # ── 1. Pydantic config validation ─────────────────────────────────────────
    try:
        from flexpipe.config import load_config

        load_config(config_path, skip_viralqc=True)
        _ok("Config validation passed (pydantic)")
    except SystemExit as exc:
        errors.append(str(exc))
        _err(f"Config validation failed: {exc}")
        # Continue with raw YAML checks even if pydantic fails
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Config validation error: {exc}")
        _err(f"Config validation error: {exc}")

    # Load raw YAML for structural checks that don't need full resolution
    try:
        config_raw = yaml.safe_load(config_path.read_text()) or {}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Could not parse config.yaml: {exc}")
        _err(f"Could not parse config.yaml: {exc}")
        _summary(errors, warnings)
        return 1

    # ── 2. Build file checks ───────────────────────────────────────────────────
    _check_subsample_yaml(build_dir, errors, warnings)
    _check_reference_gb(build_dir, errors, warnings)
    _check_clades_tsv(build_dir, errors, warnings)
    _check_mask_sites_file(config_raw, build_dir, errors, warnings)
    _check_data_source_prerequisites(config_raw, build_dir, errors, warnings)
    _check_viralqc_aliases(config_raw, errors, warnings)
    _check_clade_filter(config_raw, errors, warnings)
    _check_no_clade_source(config_raw, errors, warnings)
    _check_cache_coordinates_header(config_raw, build_dir, errors, warnings)

    _summary(errors, warnings)
    return 1 if errors else 0


def _summary(errors: list[str], warnings: list[str]) -> None:
    print()
    if warnings:
        print(f"  {len(warnings)} warning(s):")
        for w in warnings:
            print(f"    ⚠  {w}")
    if errors:
        print(f"\n  {len(errors)} error(s):")
        for e in errors:
            print(f"    ✗  {e}")
        print("\nResult: FAIL\n")
    else:
        print("Result: PASS\n")


# ── CLI entry point ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``flexpipe-validate-build``."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate a flexpipe build config.yaml before running the pipeline.\n"
            "Checks pydantic constraints plus common live-run blockers from GAPS_LOG.md."
        )
    )
    parser.add_argument(
        "config",
        help="Path to the build config.yaml (e.g. builds/yfv-brazil/config.yaml)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress per-check output; show only the summary.",
    )
    args = parser.parse_args(argv)

    from flexpipe.logging_setup import configure_logging

    configure_logging(level=logging.WARNING if args.quiet else logging.INFO)

    rc = validate_build(args.config)
    sys.exit(rc)


if __name__ == "__main__":
    main()
