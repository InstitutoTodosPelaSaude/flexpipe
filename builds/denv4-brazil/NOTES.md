# DENV-4 Brazil Build Notes

## Status

Runnable first-pass build. DENV-4 completed one end-to-end run with public
Pathoplexus data on 2026-06-07 using the maintainer-confirmed reference,
header-only clade definitions, and lightweight first-run tree settings.

## Source And Filters

- Source: Pathoplexus LAPIS organism `dengue`.
- Serotype filter: `serotype=DENV-4`.
- Public-data filter: `dataUseTerms=OPEN`.
- Minimum collection date for fetch and subsampling: `2010-01-01`.
- Open Pathoplexus aggregate check on 2026-06-06 found 660 Brazil records for DENV-4.

## Biological Inputs

- ViralQC expected virus: `Dengue virus type 4`.
- ViralQC registry reference accession: `NC_002640.1`.
- `reference.gb` is the full GenBank record for `NC_002640.1`.
- Terminal masking is set to 0/0 until calibrated on the chosen reference.
- `clades.tsv` is header-only for the first analyses. The pipeline emits an empty clades JSON when no mutation definitions are present; current coloring relies on ViralQC/Nextclade lineage assignment.
- `curation.clade_levels: 99` keeps full dengue lineage strings in `clade_truncated`.
- First-run phylo settings: `model: "JC"`, `ufboot: 0`, `date_confidence: false`, and `traits_confidence: false` per maintainer request and limited local hardware.

## Subsampling

Brazil-focal with global context:

- Brazil sample: `country == 'Brazil'`, grouped by `division`, `year`, `month`, 2 sequences per group.
- Context sample: `country != 'Brazil'`, grouped by `country`, `year`, `month`, 1 sequence per group.
- Augur cannot combine `sequences_per_group` with `max_sequences`; context is exact and uncapped.

## Run Log

- Ingest dry-run: OK on 2026-06-06 via `conda run -n nextstrain pytest -m integration tests/integration/test_ingest_wiring.py`.
- Phylo dry-run: OK on 2026-06-07 via `conda run -n nextstrain pytest -m integration tests/integration/test_phylo_wiring.py`.
- Ingest live run: OK on 2026-06-07 in `/tmp/flexpipe-runs/denv4-brazil`; fetched 994 Pathoplexus records, retained 988 after QC/filtering, and subsampled 333 sequences.
- Phylo live run: OK on 2026-06-07 in `/tmp/flexpipe-runs/denv4-brazil`; exported `/tmp/flexpipe-runs/denv4-brazil/auspice/results.json` (2.1 MB).
- Runtime notes: IQ-TREE with `JC` and no support took about 3 minutes wall time for the 333-sequence subsample. No confidence fields were emitted in branch-length or trait node data.
- Export warnings: several division/location values lacked coordinates or Auspice metadata matches; expected for Brazil-plus-global context with raw Pathoplexus geography strings.

## Open Questions

- Provide or approve DENV-4 mutation-based clade definitions for `augur clades`.
- Calibrate reference-specific terminal masking.
