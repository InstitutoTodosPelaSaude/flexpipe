# Gaps Log

## Pathoplexus per-organism filters

- Symptom: DENV1-4 are requested as separate builds, but Pathoplexus exposes dengue as a single LAPIS organism.
- Evidence: Pathoplexus API docs list `https://lapis.pathoplexus.org/dengue`; the browser exposes a `Serotype` filter.
- Suggested fix: Add a generic `pathoplexus.query_params` config map and pass it to metadata and sequence endpoints.
- Priority: P1.
- Status: Implemented in this batch for `serotype` and `dataUseTerms` filters.

## Brazil-focal builds with global context need hybrid geography

- Symptom: `region_source: division` maps Brazilian states to macro-regions but leaves non-Brazil context without continent-style `region` values.
- Evidence: DENV subsampling intentionally keeps `country != 'Brazil'` context while the display remains YFV-style `division location`.
- Suggested fix: Add an explicit hybrid geography mode or a post-curation fallback that maps `country` to continent when Brazilian division mapping is empty.
- Priority: P2.
- Status: Documented; no code change yet.

## Context exact monthly sampling cannot also be capped

- Symptom: Augur rejects a sample config with both `sequences_per_group` and `max_sequences`.
- Evidence: Local Augur probe failed with `--subsample-max-sequences: not allowed with argument --sequences-per-group`.
- Suggested fix: Document the tradeoff per build; consider a future proximal/final sampling strategy if context caps become necessary.
- Priority: P3.
- Status: DENV context uses exact uncapped `sequences_per_group: 1`.

## Mutation-based clade TSVs are not auto-derived from Nextclade lineages

- Symptom: ViralQC/Nextclade can populate metadata `clade`, but `augur clades` still needs mutation definition rows for branch labels.
- Evidence: DENV scaffolds rely on header-only `clades.tsv` placeholders; raw `augur clades` exits with `ERROR: No clades were defined`.
- Suggested fix: Add a documented import path for pathogen-specific clade TSVs; keep the no-definition branch that emits empty clade node data when metadata clades are sufficient for first analyses.
- Priority: P3.
- Status: Minimal no-definition branch implemented in `phylogenetic/Snakefile`.

## Pathoplexus FASTA IDs can diverge from metadata accessions

- Symptom: DENV Pathoplexus FASTA headers include a serotype suffix such as `PP_005ATUT.1|DENV-1`, while metadata `accessionVersion` is `PP_005ATUT.1`.
- Evidence: The first DENV-1 live run fetched 6,126 records but ViralQC and Augur filtering could not pair sequence IDs with metadata until FASTA IDs were normalized.
- Suggested fix: Keep `pathoplexus.strip_fasta_id_suffix` for organisms where LAPIS FASTA headers append non-metadata suffixes; consider auto-detection against metadata IDs later.
- Priority: P1.
- Status: Implemented for DENV configs and covered by unit tests.

## ViralQC missing joins should not become wrong-virus calls

- Symptom: Missing ViralQC rows can leave `_nc_virus` as `NaN`; comparing that directly to `expected_virus` marked all unmatched rows as wrong virus.
- Evidence: DENV-1 first live attempt warned that 6,126 sequences had the wrong/unclassified virus even though ViralQC reported `Dengue virus type 1` for matching rows.
- Suggested fix: Normalize ViralQC `seqName` values for join compatibility and treat missing virus/segment values as absent, not contamination.
- Priority: P1.
- Status: Implemented in `flexpipe.curate.viralqc_join` with unit tests.

## Empty terminal masks need an explicit no-mask path

- Symptom: `augur mask --mask-from-beginning 0 --mask-from-end 0` exits with `No masking sites provided`.
- Evidence: DENV-1 phylo failed after alignment when both terminal masks were intentionally set to `0`.
- Suggested fix: When no terminal/site/BED masks are requested, copy the alignment to the masked output path instead of invoking `augur mask`.
- Priority: P1.
- Status: Implemented in `phylogenetic/Snakefile` and covered by phylo dry-run tests.

## Tree parameters need a cheap first-pass profile

- Symptom: Template defaults (`model: MFP`, `ufboot: 1000`) are too heavy for 1k+ DENV subsamples on limited local hardware.
- Evidence: DENV-1 `MFP` entered a 968-model ModelFinder search; `GTR+I+G` remained slow in +I+G optimization; DENV-2 still needed about 48 minutes for IQ-TREE under `JC` on a 1,388-sequence subsample; maintainer requested `JC` and no support for first analyses.
- Suggested fix: Keep `parameters.ufboot: 0` as an explicit no-support mode and document first-pass vs production tree profiles per build.
- Priority: P2.
- Status: `ufboot: 0` now omits `-B`; DENV1-4 use `JC` and no support for first-run analyses.

## Date and trait confidence flags were hardcoded

- Symptom: The first-run no-support request was initially satisfied for IQ-TREE bootstraps, but `augur refine --date-confidence` and `augur traits --confidence` were still hardcoded in the phylogenetic Snakefile.
- Evidence: DENV-2 reached a long-running confidence-enabled `augur traits` step after IQ-TREE. The run was interrupted and rerun from `refine` after config switches were added.
- Suggested fix: Expose explicit `parameters.date_confidence` and `parameters.traits_confidence` booleans, defaulting to the existing behavior for current builds and disabled for DENV first-pass runs.
- Priority: P2.
- Status: Implemented in `phylogenetic/Snakefile`; DENV1-4 live outputs were run or refreshed with both confidence flags disabled.

## Geocoding dominates live ingest for location-rich builds

- Symptom: Brazil-plus-global DENV subsamples can contain hundreds of uncached `division` and `location` values, causing long Nominatim-bound coordinate runs.
- Evidence: DENV-1 coordinate generation took roughly 15 minutes from an empty cache; DENV2 still needed many new localities even when seeded from DENV1's runtime cache.
- Suggested fix: Promote a curated shared Brazil/location seed cache, normalize raw Brazilian city spellings, and consider build-time warnings for high uncached geocode counts.
- Priority: P2.
- Status: Runtime caches were manually seeded between DENV live runs; no source cache update yet.
