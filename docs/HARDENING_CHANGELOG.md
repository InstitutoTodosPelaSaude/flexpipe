# flexpipe Hardening Changelog

Date: 2026-06-06

This changelog summarizes the implementation of the hardening roadmap from
`codex_review.md`.

## Findings Addressed

- H1/M2: Build-relative paths now resolve from the build config directory and
  are written as absolute paths to `snakemake_resolved.yaml`. Subsample
  include/exclude paths are resolved as well.
- H2: Phylogenetic masking emits `--mask-sites` and BED mask flags only when
  configured.
- H3: Coordinate cache identity now includes full query context via a v2
  `query` column, with legacy cache migration.
- H4: Unknown hue assignment is stable with a persistent workdir
  `<workdir>/cache/name2hue.tsv` cache and deterministic SHA-256 fallback.
- H5: Snakemake shell blocks now quote paths and config-derived arguments with
  Snakemake quoted formatting, and config validation rejects unsafe enum/list
  values.
- M1: Coordinate cache seeding uses resolved `cfg.files.cache`.
- M3: Phylogenetic integration dry-runs cover YFV and RSV from outside the repo.
- M4: CPU-heavy rules derive tool threads from Snakemake `{threads}`, so
  `--cores` caps command rendering.
- M5: ViralQC runner is configurable with `viralqc.runner` and
  `viralqc.executable`.
- M6: Manifest provenance now records resolved config digest, resolved input
  fingerprints, git state, tool versions, ViralQC runner, and dataset
  fingerprint.
- M7: `qc_exclusion_reason` distinguishes `wrong_virus`, `wrong_segment`,
  `viralqc_quality`, and `missing_viralqc`; cross-contamination counts only
  explicit wrong-virus/wrong-segment reasons.
- M8: `run_date` is validated as `YYYY-MM-DD` and forwarded to Pathoplexus and
  NCBI fetchers as an upper date bound.
- M9: Fail-fast guards now cover missing enabled local files, malformed ViralQC
  results, and zero-sequence FASTA before ViralQC.
- M10: NCBI requires `ncbi.email` or `NCBI_EMAIL`; the placeholder fallback was
  removed.

## Files Changed

- Config/runtime: `flexpipe/config.py`, `flexpipe/run.py`, `flexpipe/paths.py`,
  `flexpipe/manifest.py`, `pyproject.toml`
- Workflows: `ingest/Snakefile`, `phylogenetic/Snakefile`
- Ingest/fetch: `flexpipe/ingest/pathoplexus.py`,
  `flexpipe/ingest/ncbi.py`, `flexpipe/ingest/merge.py`
- Curation/QC: `flexpipe/curate/viralqc_join.py`,
  `flexpipe/curate/qc_summary.py`, `flexpipe/curate/regions.py`,
  `flexpipe/curate/pipeline.py`
- Coordinates/colors: `flexpipe/geo/coordinates.py`, `flexpipe/geo/cache.py`,
  `flexpipe/colors/hues.py`
- Utilities/docs: `flexpipe/io.py`, `docs/service_contract.md`,
  `HARDENING_CHANGELOG.md`, `README.md`
- Tests: unit and integration coverage for config resolution, ingest/phylo
  dry-runs, coordinate cache migration, hue stability, validation, resource
  caps, fetch bounds, fail-fast behavior, and manifest provenance.

## Behavioral Changes

- Build configs with explicit missing input files now fail during config load.
- NCBI builds require a real email via `ncbi.email` or `NCBI_EMAIL`.
- Enabled local sequence mode exits nonzero when local files are absent.
- ViralQC exits before execution when the merged FASTA contains zero records.
- Malformed ViralQC outputs without `seqName` are fatal.
- Coordinate cache files written by current flexpipe use v2 columns. Legacy
  four-column caches remain readable.
- Ambiguous geographic values may be disambiguated in
  `results/subsampled/metadata.tsv`, for example `Springfield, Illinois`.
- Unknown clade hues no longer shift when the clade set grows.
- `run_date` now constrains Pathoplexus collection dates and NCBI publication
  dates where supported.

## Compatibility Notes

- Direct Snakemake dry-runs continue to work when given a raw build config, but
  `flexpipe-run` remains the preferred service entry point because it writes the
  resolved config, validates run dates, seeds caches, and locks the workdir.
- Existing coordinate caches are migrated in memory and rewritten in v2 format
  when cache merge runs.
- `viralqc.runner: conda` and `viralqc.executable: vqc` preserve previous
  default behavior.

## Deferred Items

- Full web UI, scheduler, deployment manifests, and ViralQC submodule changes
  remain out of scope.
- Scientific feature work unrelated to the hardening findings remains out of
  scope.
