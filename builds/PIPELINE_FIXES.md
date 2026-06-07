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

## Visualization and Trait Hardening

- Added a `continent` column during curation so Brazil builds can keep `region` as Brazilian macro-region while still inferring continent/country traits.
- Added `traits.max_states` and `traits.rare_state_label`; the phylo workflow now writes a collapsed `metadata_traits.tsv` sidecar for `augur traits` without mutating exported metadata.
- Added optional lineage parsers. DENV parsing keeps raw `clade` and adds prefix-safe `serotype`, `genotype`, `major_lineage`, and `minor_lineage` columns such as `3III_B`, never bare `B`.
- Updated color seeding to use the configured hierarchy roots and stable cached hues, with child shades derived deterministically inside the parent hue family.
