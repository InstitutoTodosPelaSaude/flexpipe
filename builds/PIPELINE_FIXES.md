# Pipeline Fixes From Batch 1

## DENV Pathoplexus ID Compatibility

- Added `pathoplexus.query_params` so the shared Pathoplexus `dengue` organism can be filtered by `serotype` and `dataUseTerms`.
- Added `pathoplexus.strip_fasta_id_suffix` for LAPIS FASTA headers like `PP_005ATUT.1|DENV-1` when metadata uses `PP_005ATUT.1`.
- Hardened ViralQC joins to match exact and pipe-normalized sequence IDs, and to avoid treating missing ViralQC rows as wrong-virus contamination.

## Optional Phylo Steps

- Header-only `clades.tsv` now produces empty clade node data instead of failing `augur clades`.
- Builds with no terminal/site/BED mask now copy aligned FASTA to the masked output path instead of invoking `augur mask` with zero masks.
- `parameters.ufboot: 0` now omits IQ-TREE `-B`, allowing first-pass no-support runs.
- Added `parameters.date_confidence` and `parameters.traits_confidence` booleans so first-pass runs can omit `augur refine --date-confidence` and `augur traits --confidence`.

## First-Run DENV Profile

- DENV1-4 use `model: "JC"`, `ufboot: 0`, `date_confidence: false`, and `traits_confidence: false` for the first analyses, per maintainer request and limited local hardware.
- Production profiles still need reference-specific terminal masks, mutation-based clade definitions, and an approved support/model policy.

## NCBI INSDC Sentinel-Value Normalization (Batch 2)

- Added `_normalize_insdc()` in `flexpipe/ingest/ncbi.py` to convert INSDC `missing: *`, `not applicable`, `not collected`, `not provided`, and `restricted access` values to empty string before writing metadata.
- Applied to both `collection_date` and `geo_loc_name` qualifiers in `parse_gb_record`.
- Root cause: NCBI returns synthetic-construct and control sequences with `'missing: synthetic construct'` as the collection date, which `augur curate format-dates` cannot parse.
- Covered by `TestNormalizeInsdc` and `TestParseGbRecordInsdc` in `tests/unit/test_ncbi.py`.

## New Builds Scaffolded (Batch 3)

- RSV-A and RSV-B Brazil (Pathoplexus): initially used blank `expected_virus` because ViralQC `results.tsv` naming differed from `blast.tsv`; now superseded by alias-backed `rsv_a` / `rsv_b`.
- OROV-L Brazil (NCBI): `expected_virus: "Oropouche virus"`, `expected_segment: "L"`, reference PP154172.1 (Tefé outbreak, 6814 bp).
- Flu H1N1/H3N2/B HA Brazil (NCBI): initially used blank virus/segment filters because ViralQC labels were strain-specific or `HA`/`4` mixed; now superseded by alias-backed flu virus keys and `expected_segment: "ha"`.
- All new builds use the first-pass profile: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`.
- Integration tests cover dry-run wiring for all new builds; 51 integration tests pass.

## Visualization and Trait Hardening

- Added a `continent` column during curation so Brazil builds can keep `region` as Brazilian macro-region while still inferring continent/country traits.
- Added `traits.max_states` and `traits.rare_state_label`; the phylo workflow now writes a collapsed `metadata_traits.tsv` sidecar for `augur traits` without mutating exported metadata.
- Added optional lineage parsers. DENV parsing keeps raw `clade` and adds prefix-safe `serotype`, `genotype`, `major_lineage`, and `minor_lineage` columns such as `3III_B`, never bare `B`.
- Updated color seeding to use the configured hierarchy roots and stable cached hues, with child shades derived deterministically inside the parent hue family.

## Follow-Up Hardening From Multi-Build Learnings

- Added `flexpipe/data/viralqc/aliases.yaml` plus `viralqc.aliases_file` overrides. `expected_virus` and `expected_segment` now resolve through alias/regex entries before falling back to exact matching. RSV and flu configs use operational keys (`rsv_a`, `rsv_b`, `flu_a_h1n1`, `flu_a_h3n2`, `flu_b`, `ha`) instead of blank workarounds.
- Added `flexpipe-reference-mask` and `flexpipe/data/phylo/reference_mask_profiles.yaml`. The tool derives terminal BED masks from explicit UTR annotations, UTR-like qualifiers on other feature types, or CDS/gene boundaries, with a guardrail against excessive masking. New DENV, ZIKV, CHIKV, RSV-A/B, OROV-L, and flu HA builds now point to `masks/reference_terminal.bed`.
- Added `flexpipe-normalize-dates` and `flexpipe/data/curation/date_formats.yaml`. The ingest workflow now normalizes flexible year/year-month/full-date strings before `augur curate format-dates` and writes `results/ingest/date_normalization.tsv`.
- Added a bundled shared geocode seed cache at `flexpipe/data/geo/cache_coordinates.tsv` plus `coordinates.shared_cache` override. Workdir caches are seeded from shared entries first and build-specific entries second, so manual build seeds still win.
- Added `builds/SCAFFOLD_CHECKLIST.md` to turn the learned archetypes into a concise copy-forward checklist.
