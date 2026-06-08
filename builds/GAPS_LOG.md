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

## NCBI INSDC sentinel dates break augur curate format-dates

- Symptom: `augur curate format-dates` exits with `Unable to format date string 'missing: synthetic construct'` during ZIKV live ingest.
- Evidence: NCBI returns synthetic-construct records with INSDC sentinel values (`missing: <reason>`, `not applicable`, etc.) in the `collection_date` qualifier. flexpipe-fetch-ncbi previously passed these through verbatim.
- Suggested fix: Normalize INSDC sentinel values (`missing:*`, `not applicable`, `not collected`, `not provided`) to empty string in `parse_gb_record()` before writing the metadata TSV, so `augur filter --exclude-where date=` can drop them cleanly.
- Priority: P1.
- Status: Implemented in `flexpipe/ingest/ncbi.py` with unit tests in `tests/unit/test_ncbi.py`.

## Flu HA expected_virus cannot use a single stable string

- Symptom: `expected_virus` filtering for flu builds requires an exact match against the `virus` column in ViralQC output, which originates from the BLAST database `virus_name` field. For flu, each RefSeq reference entry has a strain-specific name (e.g. "Influenza A virus (A/California/07/2009(H1N1))"), so no single string covers all H1N1 pdm09 sequences — different strains produce different BLAST hits.
- Evidence: The blast.tsv entries for flu A H1N1 pdm09 are all attributed to A/California/07/2009; other strains (H3N2, H7N9) each have distinct per-strain names. A global `expected_virus: "Influenza A virus"` would never match since names include strain designations.
- Suggested fix: Leave `expected_virus: ""` for flu builds; rely on `expected_segment: "4"` (HA = segment 4 in NCBI RefSeq flu) to filter non-HA segments. A future improvement could use partial-match (prefix or regex) in viralqc_join.py.
- Priority: P3 (documentation-only; not blocking first analyses).
- Status: Documented; flu builds use `expected_segment: "4"` and empty `expected_virus`.

## Flu ViralQC segment naming is "HA"/"NA" not numeric "4"/"6"

- Symptom: Flu B ingest dropped all 80,028 sequences as `genome_quality=D` (wrong_segment). H1N1 only retained the 3,502 sequences with segment label "4", dropping 21,620 labeled "HA".
- Evidence: ViralQC `results.tsv` segment column uses string names ("HA", "NA", "NP") for flu B (and most flu A sequences), while config had `expected_segment: "4"`. The exact-match comparison fails for named segments.
- Suggested fix: Set `expected_segment: ""` for all flu builds; rely on Nextclade alignment quality (A/B) to exclude non-HA segments (NA, NP sequences aligned to an HA reference get poor coverage → genome_quality C/D).
- Priority: P1 (blocked flu live runs).
- Status: Fixed; `expected_segment: ""` in all three flu configs.

## Non-ISO dates in NCBI flu records break `augur curate format-dates`

- Symptom: H3N2 ingest failed with `Unable to format date string '11/06/2004'`; 183 records had MM/DD/YYYY format dates.
- Evidence: Some NCBI GenBank flu records use US-style slash-delimited dates not in the expected-date-formats list (`'%Y-%m-%d' '%Y-%m' '%Y' '%d-%b-%Y' '%b-%Y'`).
- Suggested fix: Add `'%m/%d/%Y'` to expected-date-formats and `--failure-reporting warn` to `augur curate format-dates` in `ingest/Snakefile` so unexpected formats produce a warning rather than a hard failure.
- Priority: P1 (blocked H3N2 live run).
- Status: Fixed in Snakefile; MM/DD/YYYY dates in cached H3N2 metadata patched to ISO format.

## INSDC `"unknown"` date sentinel not covered by _normalize_insdc()

- Symptom: Flu HA ingests failed with `Unable to format date string 'unknown'` in `augur curate format-dates`.
- Evidence: NCBI flu GenBank records use `"unknown"` as a collection_date qualifier value; this was not in the initial `_INSDC_MISSING_PREFIXES` tuple. `"none"` and `"null"` also encountered in large NCBI datasets.
- Suggested fix: Add `"unknown"`, `"none"`, `"null"` to `_INSDC_MISSING_PREFIXES` in `flexpipe/ingest/ncbi.py`.
- Priority: P1 (blocked all three flu live runs).
- Status: Fixed; covered by new test cases in `TestNormalizeInsdc`.

## New build subsample.yaml files used wrong `subsamples:` key instead of `samples:`

- Symptom: RSV-A ingest (second attempt) failed with `Unexpected property 'subsamples'` / `Missing required property 'samples'` from augur subsample schema validation.
- Evidence: Batch 3 scaffold generated `subsamples:` with inline `--query "..."` filter strings and string-form `group_by`. Augur subsample expects `samples:` with plain `query:` strings and list-form `group_by:`. ZIKV/CHIKV had the correct format (ran successfully); RSV-A/B, OROV-L, flu H1N1/H3N2/B used the wrong format.
- Suggested fix: Use DENV subsample.yaml as the authoritative template for future scaffolds.
- Priority: P1 (blocked RSV/OROV/flu live runs).
- Status: Fixed in all 5 affected builds (rsv-b-brazil, orov-l-brazil, flu-h1n1/h3n2/b-ha-brazil).

## ViralQC results.tsv `virus` column differs from blast.tsv `virus_name`

- Symptom: RSV-A ingest dropped all 40,657 sequences as `genome_quality=D` (wrong_virus) despite correct Pathoplexus fetch.
- Evidence: `expected_virus: "human respiratory syncytial virus"` was derived from `viralQC/datasets/blast.tsv virus_name` for NC_038235.1. However, ViralQC's `results.tsv` `virus` column uses Nextclade dataset naming (`"Respiratory syncytial virus A"`, `"Human respiratory syncytial virus A"`), not the BLAST db virus_name. The exact-match comparison in `viralqc_join.py` flagged every RSV-A sequence as wrong_virus.
- Suggested fix: For Pathoplexus builds the organism slug already restricts the fetch; leave `expected_virus: ""` for RSV-A and RSV-B. A broader fix would make `viralqc_join.py` use case-insensitive substring matching so blast.tsv-derived names work across both name formats.
- Priority: P1 (blocked RSV live runs).
- Status: Fixed by setting `expected_virus: ""` in rsv-a-brazil and rsv-b-brazil configs.

## Geocoding dominates live ingest for location-rich builds

- Symptom: Brazil-plus-global DENV subsamples can contain hundreds of uncached `division` and `location` values, causing long Nominatim-bound coordinate runs.
- Evidence: DENV-1 coordinate generation took roughly 15 minutes from an empty cache; DENV2 still needed many new localities even when seeded from DENV1's runtime cache.
- Suggested fix: Promote a curated shared Brazil/location seed cache, normalize raw Brazilian city spellings, and consider build-time warnings for high uncached geocode counts.
- Priority: P2.
- Status: Runtime caches were manually seeded between DENV live runs; no source cache update yet.
