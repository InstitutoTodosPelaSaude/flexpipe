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
- Suggested fix: Add an explicit `continent` column derived from `country`, while leaving `region` as the Brazilian macro-region for `region_source: division`.
- Priority: P2.
- Status: Superseded by implemented `continent` curation and continent-aware traits/colors.

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
- Suggested fix: Use an external ViralQC alias registry with operational keys such as `flu_a_h1n1`, `flu_a_h3n2`, and `flu_b` instead of exact one-off strings.
- Priority: P3 (documentation-only; not blocking first analyses).
- Status: Superseded. `flexpipe/data/viralqc/aliases.yaml` now provides alias/regex matching, and flu configs use alias-backed `expected_virus` keys.

## Flu ViralQC segment naming is "HA"/"NA" not numeric "4"/"6"

- Symptom: Flu B ingest dropped all 80,028 sequences as `genome_quality=D` (wrong_segment). H1N1 only retained the 3,502 sequences with segment label "4", dropping 21,620 labeled "HA".
- Evidence: ViralQC `results.tsv` segment column uses string names ("HA", "NA", "NP") for flu B (and most flu A sequences), while config had `expected_segment: "4"`. The exact-match comparison fails for named segments.
- Suggested fix: Use an external segment alias entry where `ha` accepts both `HA` and `4`.
- Priority: P1 (blocked flu live runs).
- Status: Superseded. `expected_segment: "ha"` is now alias-backed in all three flu configs.

## Non-ISO dates in NCBI flu records break `augur curate format-dates`

- Symptom: H3N2 ingest failed with `Unable to format date string '11/06/2004'`; 183 records had MM/DD/YYYY format dates.
- Evidence: Some NCBI GenBank flu records use US-style slash-delimited dates not in the expected-date-formats list (`'%Y-%m-%d' '%Y-%m' '%Y' '%d-%b-%Y' '%b-%Y'`).
- Suggested fix: Normalize flexible dates before Augur using an external date policy, then keep `augur curate format-dates --failure-reporting warn` as a guardrail.
- Priority: P1 (blocked H3N2 live run).
- Status: Superseded by `flexpipe-normalize-dates` and `flexpipe/data/curation/date_formats.yaml`; Augur warning mode remains as a downstream guardrail.

## INSDC `"unknown"` date sentinel not covered by _normalize_insdc()

- Symptom: Flu HA ingests failed with `Unable to format date string 'unknown'` in `augur curate format-dates`.
- Evidence: NCBI flu GenBank records use `"unknown"` as a collection_date qualifier value; this was not in the initial `_INSDC_MISSING_PREFIXES` tuple. `"none"` and `"null"` also encountered in large NCBI datasets.
- Suggested fix: Normalize these both at NCBI ingest and in the generic pre-Augur date normalizer.
- Priority: P1 (blocked all three flu live runs).
- Status: Fixed and generalized. `_normalize_insdc()` still handles NCBI-specific qualifiers; `flexpipe-normalize-dates` handles table-level sentinels before Augur.

## New build subsample.yaml files used wrong `subsamples:` key instead of `samples:`

- Symptom: RSV-A ingest (second attempt) failed with `Unexpected property 'subsamples'` / `Missing required property 'samples'` from augur subsample schema validation.
- Evidence: Batch 3 scaffold generated `subsamples:` with inline `--query "..."` filter strings and string-form `group_by`. Augur subsample expects `samples:` with plain `query:` strings and list-form `group_by:`. ZIKV/CHIKV had the correct format (ran successfully); RSV-A/B, OROV-L, flu H1N1/H3N2/B used the wrong format.
- Suggested fix: Use DENV subsample.yaml as the authoritative template for future scaffolds.
- Priority: P1 (blocked RSV/OROV/flu live runs).
- Status: Fixed in all 5 affected builds (rsv-b-brazil, orov-l-brazil, flu-h1n1/h3n2/b-ha-brazil).

## ViralQC results.tsv `virus` column differs from blast.tsv `virus_name`

- Symptom: RSV-A ingest dropped all 40,657 sequences as `genome_quality=D` (wrong_virus) despite correct Pathoplexus fetch.
- Evidence: `expected_virus: "human respiratory syncytial virus"` was derived from `viralQC/datasets/blast.tsv virus_name` for NC_038235.1. However, ViralQC's `results.tsv` `virus` column uses Nextclade dataset naming (`"Respiratory syncytial virus A"`, `"Human respiratory syncytial virus A"`), not the BLAST db virus_name. The exact-match comparison in `viralqc_join.py` flagged every RSV-A sequence as wrong_virus.
- Suggested fix: Use an external ViralQC alias registry where `rsv_a` and `rsv_b` accept both Nextclade dataset names and BLAST-style names.
- Priority: P1 (blocked RSV live runs).
- Status: Superseded. RSV configs now use alias-backed `expected_virus` keys instead of blank workarounds.

## Geocoding dominates live ingest for location-rich builds

- Symptom: Brazil-plus-global DENV subsamples can contain hundreds of uncached `division` and `location` values, causing long Nominatim-bound coordinate runs.
- Evidence: DENV-1 coordinate generation took roughly 15 minutes from an empty cache; DENV2 still needed many new localities even when seeded from DENV1's runtime cache.
- Suggested fix: Promote a curated shared Brazil/location seed cache, normalize raw Brazilian city spellings, and consider build-time warnings for high uncached geocode counts.
- Priority: P2.
- Status: Partially implemented. A bundled shared seed cache now seeds workdirs before build-specific caches; warning/reporting for high uncached counts is still deferred.

## Reference-derived terminal masks were missing for new first-pass builds

- Symptom: New builds had `mask_5prime: 0`, `mask_3prime: 0`, and no BED masks, so first-pass exports were intentionally unmasked.
- Evidence: `BUILD_ROSTER.md` listed terminal masks as uncalibrated for DENV, ZIKV, CHIKV, RSV-A/B, OROV-L, and flu HA builds.
- Suggested fix: Derive first-draft terminal BED masks from GenBank annotations with a flexible profile that recognizes explicit UTR features and UTR-like annotations on other feature types, with CDS/gene boundary fallback and guardrails.
- Priority: P1.
- Status: Implemented via `flexpipe-reference-mask`, `flexpipe/data/phylo/reference_mask_profiles.yaml`, and per-build `masks/reference_terminal.bed` files. These are production aids and still need biological review before surveillance use.

## No-dataset virus QC strategy

- Symptom: `viralqc.mode: run` silently drops all sequences for viruses absent from the ViralQC BLAST reference set (e.g. Mayaro virus). BLAST mislabels the sequences as a related virus; with `expected_virus` set, all are flagged `wrong_virus` → grade D → empty build.
- Evidence: Mayaro virus (MAYV) is absent from `viralQC/datasets/blast.tsv` (which has Chikungunya, Una, Madariaga, VEEV, Ross River, but not Mayaro). Confirmed by `grep -i mayaro viralQC/datasets/blast.tsv` returning empty.
- A second footgun: `qc.required_columns` defaults to `["strain","date","clade"]`. With no clade source, `augur filter --exclude-where clade=` drops every row.
- Suggested fix: Use `viralqc.mode: skip` with `genome_size` set for length-based coverage; remove `clade` from `required_columns` and `traits.columns`. Add a validator check that errors when `mode=skip` and `clade` is in `required_columns`.
- Priority: P1 (blocks entire build for undataset pathogens).
- Status: Implemented. `synthesize_viralqc.py` computes length-based coverage when `genome_size > 0`. `flexpipe/validate.py::_check_no_clade_source` errors on `clade` in `required_columns` for skip-mode builds, and warns on traits/clade_filter issues. Recipe in `docs/viralqc-integration.md` and `builds/SCAFFOLD_CHECKLIST.md`. Reference build: `builds/mayv-global/` (live run: 105 fetched, 101 QC-passed, 95 subsampled, Auspice output produced 2026-06-08).
