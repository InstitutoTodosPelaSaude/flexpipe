# DENV-3 Brazil Build Notes

## Status

Runnable first-pass build. DENV-3 completed one end-to-end run with public
Pathoplexus data on 2026-06-07 using the maintainer-confirmed reference,
header-only clade definitions, and lightweight first-run tree settings.

## Source And Filters

- Source: Pathoplexus LAPIS organism `dengue`.
- Serotype filter: `serotype=DENV-3`.
- Public-data filter: `dataUseTerms=OPEN`.
- Minimum collection date for fetch and subsampling: `2010-01-01`.
- Open Pathoplexus aggregate check on 2026-06-06 found 514 Brazil records for DENV-3.

## Biological Inputs

- ViralQC expected virus: `Dengue virus type 3`.
- ViralQC registry reference accession: `NC_001475.2`.
- `reference.gb` is the full GenBank record for `NC_001475.2`.
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
- Ingest live run: OK on 2026-06-07 in `/tmp/flexpipe-runs/denv3-brazil`; fetched 2,254 Pathoplexus records, retained 2,248 after QC/filtering, and subsampled 516 sequences.
- Phylo live run: OK on 2026-06-07 in `/tmp/flexpipe-runs/denv3-brazil`; exported `/tmp/flexpipe-runs/denv3-brazil/auspice/results.json` (3.8 MB).
- Runtime notes: IQ-TREE with `JC` and no support took about 6 minutes wall time for the 516-sequence subsample. No confidence fields were emitted in branch-length or trait node data.
- Export warnings: several division/location values lacked coordinates or Auspice metadata matches; expected for Brazil-plus-global context with raw Pathoplexus geography strings.

## Open Questions

- Provide or approve DENV-3 mutation-based clade definitions for `augur clades`.
- Calibrate reference-specific terminal masking.
