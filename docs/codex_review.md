# Codex Independent Review - flexpipe

Date: 2026-06-06

## Scope

This is an independent review of the current `flexpipe` repository as a software system for
automated Nextstrain builds. I focused on correctness, reliability, multi-build extensibility,
operational readiness, and the long-term path toward a web service that reruns builds
automatically.

I did not modify source code. I only added this review file. I also left the existing
`review_20260605.md` untracked file untouched.

## Executive Summary

The repository is in a much stronger state than a loose collection of scripts. The package layout
is coherent, core curation logic is decomposed into testable modules, the workdir isolation model
is the right direction, and the current unit suite is substantial. The orchestrator, file lock,
manifest, pydantic config, ingest/phylo split, and RSV scaffold all point toward a pipeline that can
become a reliable multi-virus service.

The main risks are not in basic Python style. The verified checks pass. The important remaining
risks are workflow-level and service-level:

- Several build paths are still relative to the caller's current working directory.
- The phylogenetic mask rule renders an invalid command when `mask_sites` is empty, which is the
  documented default for new builds.
- Coordinate caching can conflate same-named places in different parents.
- "Hash-based" color assignment is not actually stable when the set of clades changes.
- Snakemake shell commands interpolate config values without robust quoting or an explicit trust
  boundary.

My overall take: this is a good foundation for expanding beyond YFV, but I would fix the high
priority items below before relying on it for unattended scheduled runs or a public/internal web
service.

## Verification Performed

All commands below were run from `/Users/fmoreira/Desktop/projects/flexpipe` unless noted.

- `conda run -n nextstrain pytest`
  - Result: 351 passed, 8 integration tests deselected.
- `conda run -n nextstrain pytest -m integration`
  - First run failed because the sandbox blocked Snakemake's runtime cache under
    `~/Library/Caches`.
  - Re-run with approved cache access passed: 8 passed.
- `conda run -n nextstrain pytest --cov=flexpipe --cov-report=term-missing --cov-fail-under=60`
  - Result: 351 passed, 8 deselected, total coverage 68.88%.
- `conda run -n nextstrain ruff check .`
  - Result: passed.
- `conda run -n nextstrain black --check .`
  - Result: passed.
- `conda run -n nextstrain mypy flexpipe/ --ignore-missing-imports`
  - Result: passed.
- Targeted phylogenetic dry-run for the RSV mask output:
  - Confirmed that `mask_sites: ""` renders a bare `--mask-sites` flag.
- Targeted phylogenetic dry-run from `/private/tmp` with absolute Snakefile/config paths:
  - Confirmed that relative build file paths are resolved against the caller cwd and fail outside
    the repo root.

I did not run a full live YFV build because that would require external network services, ViralQC
datasets, MAFFT/IQ-TREE runtime, and substantial compute.

## Strengths

- The workdir-first design is the right architecture for scheduled builds. `WorkdirPaths` centralizes
  many generated artifacts, and `flexpipe-run` does not intentionally mutate build directories.
- The Python package is installable and has clear console entry points.
- Pydantic validation catches several bad config states early.
- Curation, region mapping, host normalization, ViralQC joining, color generation, and cache merging
  are split into testable modules.
- The test suite is broad for pure Python behavior. Golden-style curation tests are especially useful.
- The ingest-to-phylo boundary check and `qc.min_sequences` guardrail are valuable production
  protections.
- The workdir-level `filelock` is a pragmatic fix for concurrent runs sharing the same output tree.
- Docker and CI exist, and the Docker context excludes the large ViralQC submodule/datasets.

## High Priority Findings

### H1. Build file paths are cwd-dependent

Evidence:

- `flexpipe/run.py:99-118` invokes Snakemake without setting `cwd`.
- `flexpipe/config.py:387-392` writes the resolved Snakemake config while preserving raw relative
  paths from the build config.
- The Snakefiles use those paths directly, e.g. `phylogenetic/Snakefile:30`,
  `phylogenetic/Snakefile:211`, `phylogenetic/Snakefile:238`, and
  `ingest/Snakefile:258-263`.

I verified this with a phylo dry-run launched from `/private/tmp` using absolute paths for both the
Snakefile and build config. Snakemake failed with:

```text
Missing input files for rule align:
    affected files:
        builds/rsv-global/reference.gb
```

Impact:

This will surprise schedulers, web workers, cron jobs, Docker invocations with external config
mounts, or any user who runs `flexpipe-run` outside the repo root. It also weakens the promise that
a build is fully described by `(config, workdir, run-date)`.

Recommended fix:

- Resolve every path-like config value relative to the build config directory or repo root at config
  load time, then write absolute paths into `snakemake_resolved.yaml`.
- Include at least `files.*`, `local_sequences.*`, `parameters.mask_sites_file`,
  `coordinates.force_file`, `regions.*`, `curation.host_rules`, `colours.hue_tables.*`, and paths
  embedded in `subsample.yaml` (`include`, `exclude`, `defaults.exclude`).
- Add a regression test that runs a Snakemake dry-run from a cwd outside the repo.

### H2. `mask_sites: ""` renders an invalid `augur mask` command

Evidence:

- `ParametersConfig.mask_sites` defaults to `""` in `flexpipe/config.py:52`.
- The RSV scaffold sets `mask_sites: ""` in `builds/rsv-global/config.yaml:17`.
- `phylogenetic/Snakefile:72-78` always emits `--mask-sites {params.mask_sites}`.

The targeted RSV dry-run rendered:

```text
augur mask ... --mask-sites --output /private/tmp/.../masked.fasta
```

Impact:

The documented safe default for new builds can fail at the phylogenetic stage. This is exactly the
kind of issue that will block adding new viruses.

Recommended fix:

- Build optional flags conditionally:

```python
mask_sites_flag = f"--mask-sites {parameters.mask_sites}" if str(parameters.mask_sites).strip() else ""
mask_bed_flag = f"--mask {_mask_sites_file}" if _mask_sites_file else ""
```

- Use the conditional flags in the shell command.
- Add phylo dry-run tests for both empty and non-empty `mask_sites`.

### H3. Coordinate caching can assign wrong coordinates to same-named places

Evidence:

- `flexpipe/geo/coordinates.py:201-225` uses `target = place_parts[-1]` as the cache/output key.
- `flexpipe/geo/coordinates.py:230-231` appends only `level`, `target`, latitude, longitude to the
  workdir cache.
- `flexpipe/geo/cache.py:47` deduplicates on only `(level, name)`.

Impact:

For builds that geocode locations below country/state level, two cities with the same name in
different divisions or countries will collide. The first coordinate will be reused for later rows.
This is a serious correctness risk for global builds and for any future web service that accumulates
coordinate caches over time.

Recommended fix:

- Store cache keys with parent context, e.g. `(level, name, parent_1, parent_2)` or a normalized
  full query string.
- Preserve the Augur lat-longs output format separately from the internal cache format.
- Add tests for duplicate city names in different countries/states.

### H4. Clade hues are not stable when new clades appear

Evidence:

- `flexpipe/colors/hues.py:85-102` implements `spread_hues()` by sorting the current names and
  spreading them across the wheel.
- `flexpipe/colors/hues.py:142-147` uses that spread for unknown clades.
- The module docstring describes hash-based deterministic hues, but no hash is used.

Impact:

The same clade can receive a different hue after another clade appears or disappears. That is bad
for a service where users compare builds over time.

Recommended fix:

- Use a true stable hash from category name to hue bucket, with deterministic collision handling.
- Better: maintain a per-build persisted color mapping in the workdir or build config and append
  new categories without changing old ones.
- Add a test that hue("A") remains unchanged when "B" is added.

### H5. Snakemake shell commands interpolate config values without a clear trust boundary

Evidence:

Many shell blocks insert paths and config strings directly, for example:

- `ingest/Snakefile:114-121`
- `ingest/Snakefile:147-155`
- `ingest/Snakefile:289-297`
- `phylogenetic/Snakefile:72-78`
- `phylogenetic/Snakefile:97-104`

Impact:

If build configs are fully trusted and generated only by maintainers, this is mainly a path-with-spaces
and robustness issue. If the future web service lets users upload or edit configs, this becomes a
command-injection boundary.

Recommended fix:

- Use Snakemake's quoted formatting (`{input:q}`, `{params:q}`, `{output:q}`) where applicable.
- Validate config fields more strictly: enums for model/root/coalescent/date inference where possible,
  positive ints for threads/bootstrap, constrained strings for traits/columns, and path types for files.
- For web service mode, treat build configs as data, not shell fragments.

## Medium Priority Findings

### M1. `files.cache` is configured but ignored for cache seeding

Evidence:

- `builds/yfv-brazil/config.yaml:4` and `builds/rsv-global/config.yaml:4` define `files.cache`.
- `flexpipe/run.py:65-73` always seeds from `build_dir / "cache_coordinates.tsv"`.
- `ingest/Snakefile:53-55` always uses `<workdir>/cache/cache_coordinates.tsv`.

Impact:

New builds cannot rename or relocate their coordinate seed via config, despite the schema suggesting
they can.

Recommended fix:

Resolve and use `cfg.files.cache` when seeding the workdir cache.

### M2. Override paths are validated relative to cwd

Evidence:

- `flexpipe/config.py:226-257` checks override paths with `Path(path).exists()`.
- `flexpipe/data/__init__.py:45-53` and `flexpipe/data/__init__.py:76-84` load override paths the
  same way.

Impact:

Build-relative override files will fail unless the process happens to run from the expected cwd.
This is part of H1, but it also affects pure Python entry points such as `flexpipe-curate`.

Recommended fix:

Pass the build config directory into path resolution, or convert all config path fields to absolute
paths in `load_config()`.

### M3. Current integration tests do not cover the phylogenetic Snakefile

Evidence:

- `tests/integration/test_ingest_wiring.py` covers ingest DAG dry-runs only.
- The `mask_sites` bug above was not caught by the current test suite.

Recommended fix:

- Add phylo dry-run tests for YFV and RSV scaffold.
- Include tests for optional arguments (`mask_sites`, `mask_sites_file`), cwd independence, thread
  rendering, and required export inputs.

### M4. Snakemake `--cores` and service resource limits are not fully enforced

Evidence:

- Rules use `options.threads` in params, e.g. `ingest/Snakefile:137-139`,
  `phylogenetic/Snakefile:30-32`, and `phylogenetic/Snakefile:87-91`.
- The rules do not declare Snakemake `threads:` resources.

Impact:

`flexpipe-run --cores 1` can still run tools with `options.threads: 4`. This matters when multiple
builds run concurrently in a service.

Recommended fix:

- Add `threads:` declarations to CPU-heavy rules.
- Derive tool thread counts from Snakemake's rule threads, not independently from config.
- Define service-level CPU/memory quotas per build.

### M5. ViralQC execution is hard-wired to `conda run`

Evidence:

- `ingest/Snakefile:147` uses `conda run -n {params.conda_env} vqc run`.
- `scripts/install_viralqc.sh:152-158` warns that this is incompatible with mamba/micromamba-only
  installs.

Impact:

The install script supports multiple environment managers, but runtime does not. This can break
container or service deployments that do not expose `conda`.

Recommended fix:

- Make the ViralQC runner configurable (`conda`, `mamba`, direct executable path, or container).
- Consider calling a resolved `vqc` executable directly in controlled production images.

### M6. Manifest provenance is useful but incomplete

Evidence:

- `flexpipe/manifest.py:84-90` hashes only `subsample.yaml`, `clades.tsv`, `reference.gb`, and
  `run_date` in addition to the main config.

Impact:

Runs can differ without a manifest hash change: `auspice_config.json`, `keep.txt`, `ignore.txt`,
coordinate seeds, host/region/color override files, local sequences, local metadata, and ViralQC
dataset contents are not represented.

Recommended fix:

- Hash every resolved build input file.
- Record git commit SHA, dirty flag, package version, Snakemake version, Augur version, IQ-TREE
  version, MAFFT version, ViralQC version, and ViralQC dataset identifier/digest.
- Store the fully resolved config and resolved subsample config path/digest in the manifest.

### M7. QC summary overstates cross-contamination

Evidence:

- `flexpipe/curate/qc_summary.py:122-125` reports all grade `D` sequences as
  `cross_contamination_count`.
- But grade `D` can mean general low quality, not necessarily wrong virus/segment.

Impact:

The QC report can mislead operators and users.

Recommended fix:

- In `join_viralqc()`, add an explicit reason column such as `qc_exclusion_reason` with values like
  `wrong_virus`, `wrong_segment`, `nextclade_quality`, `low_coverage`.
- Count cross-contamination from that reason column only.

### M8. `run_date` is not validated and is not used as a fetch upper bound

Evidence:

- `flexpipe/run.py:308-319` accepts any string for `--run-date`.
- `flexpipe/ingest/pathoplexus.py:226-231` and `flexpipe/ingest/ncbi.py:209-214` apply only a lower
  date bound.

Impact:

Invalid dates fail later. Scheduled runs can fetch records beyond the intended analysis date and
drop them only during subsampling, which is less reproducible and less efficient.

Recommended fix:

- Validate `--run-date` as `YYYY-MM-DD`.
- Decide whether future dates should be rejected.
- Pass run-date into source queries as an upper bound where APIs support it.

### M9. Some critical data-contract failures are warnings or silent fallbacks

Evidence:

- `flexpipe/ingest/merge.py:211-216` only warns when `local_sequences.enabled=true` but files are
  missing.
- `flexpipe/curate/viralqc_join.py:54-132` silently skips a ViralQC file without `seqName`.
- `flexpipe/ingest/ncbi.py:235-253` writes empty outputs for zero NCBI records, after which ViralQC
  may fail less clearly.

Impact:

Unattended service runs need crisp, actionable failure states. Silent fallbacks can turn input
configuration problems into empty or misleading downstream results.

Recommended fix:

- Fail fast when local sequence merging is enabled but files are missing.
- Fail fast when ViralQC output is missing required columns after the `viralqc` rule succeeds.
- Add a clear zero-record preflight before ViralQC.

### M10. NCBI production usage should require a real contact email

Evidence:

- `flexpipe/ingest/ncbi.py:196` falls back to `pipeline@example.com`.

Impact:

NCBI asks automated clients to provide a real email. A service should not run large recurring Entrez
queries with a placeholder contact.

Recommended fix:

- Require `ncbi.email` or `NCBI_EMAIL` for `data_source: ncbi`.
- Treat API keys as secrets in the future web service.

## Lower Priority Findings

- `flexpipe/curate/regions.py:194` uses module-level `_BRAZIL_CANONICAL` inside
  `_parse_brazil_division()`, even when override Brazil maps are supplied. If custom division maps
  are ever used, parsing and region lookup may disagree.
- `flexpipe/geo/cache.py:55-58` logs a misleading "new" count; the formula can report old entries
  rather than newly added entries.
- `flexpipe/io.py:62-64` says `load_tsv()` asserts `.tsv` or `.txt`, but the implementation just
  reads the path as TSV without extension checks.
- The legacy top-level `config/` build files and the newer `builds/` layout coexist. That may be
  intentional for backward compatibility, but it increases operator confusion.
- Coverage is healthy overall, but CLI entry points, `colors/scheme.py`, and live ingest paths remain
  lightly covered because they are mostly exercised via subprocesses or not at all.

## Test Coverage Gaps To Close

The current suite is strong for pure Python curation behavior. The next tranche should focus on
workflow and production contracts:

- Phylogenetic dry-run tests for every scaffold build.
- Cwd-independence tests for `flexpipe-run` and direct Snakemake invocation.
- Tests that optional flags are absent when config values are empty.
- Coordinate cache tests with duplicate city names under different parent locations.
- Hue stability tests across category additions/removals.
- Tests for build-relative override paths.
- Tests for zero-result fetches and malformed ViralQC outputs.
- A small end-to-end smoke test with tiny local fixtures and mocked/no-op external tools, so the
  entire ingest-to-export wiring can run without network or heavy phylogenetics.

## Suggested Hardening Roadmap

1. Fix path resolution and `mask_sites` rendering first.
   These are concrete correctness blockers for multi-build usage.

2. Add phylo dry-run integration tests.
   They should run in CI alongside the existing ingest dry-runs and catch optional-flag regressions.

3. Make geocoding and colors stable over time.
   Coordinate correctness and visual continuity matter a lot for a public-facing build service.

4. Tighten config validation and shell quoting.
   This is required before configs are user-editable or accepted through a web UI.

5. Expand manifest/provenance.
   A service needs to explain exactly why a build changed.

6. Define the service execution contract.
   Include per-build workdir layout, resource quotas, retry policy, data source credentials, cache
   ownership, logs/status schema, and how restricted data-use terms are enforced.

## Final Assessment

`flexpipe` is on a promising trajectory. It is already much more maintainable than an ad hoc
Nextstrain script tree, and the recent refactor clearly moved important behavior into testable
Python modules. The remaining work is mostly about making implicit assumptions explicit: path roots,
optional command flags, coordinate identity, color persistence, resource limits, and trust boundaries.

I would be comfortable continuing to add new viruses after H1-H2 are fixed and phylo dry-runs are in
CI. I would not put this behind an unattended web service until H1-H5 and the provenance/resource
items are addressed.
