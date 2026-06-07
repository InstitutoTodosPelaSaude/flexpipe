# DENV-1 Brazil Build Notes

## Status

Runnable first-pass build. DENV-1 completed one end-to-end run with public
Pathoplexus data on 2026-06-07 using the maintainer-confirmed reference,
header-only clade definitions, and lightweight first-run tree settings.

## Source And Filters

- Source: Pathoplexus LAPIS organism `dengue`.
- Serotype filter: `serotype=DENV-1`.
- Public-data filter: `dataUseTerms=OPEN`.
- Minimum collection date for fetch and subsampling: `2010-01-01`.
- Open Pathoplexus aggregate check on 2026-06-06 found 2,440 Brazil records for DENV-1.

## Biological Inputs

- ViralQC expected virus: `Dengue virus type 1`.
- ViralQC registry reference accession: `NC_001477.1`.
- `reference.gb` is the full GenBank record for `NC_001477.1`.
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
- Ingest live run: OK on 2026-06-06/2026-06-07 in `/tmp/flexpipe-runs/denv1-brazil-fixed`; fetched 6,126 Pathoplexus records, retained 6,118 after QC/filtering, and subsampled 1,286 sequences.
- Phylo live run: OK on 2026-06-07 in `/tmp/flexpipe-runs/denv1-brazil-fixed`; exported `/tmp/flexpipe-runs/denv1-brazil-fixed/auspice/results.json` (1.6 MB after no-confidence tail refresh).
- Runtime notes: empty/zero terminal masks originally caused `augur mask` to fail until the no-mask copy path was implemented. `MFP`, then `GTR+I+G`, were too slow for this first-pass run on local hardware; maintainer requested `JC` with no statistical support. The phylo tail was rerun after adding explicit `date_confidence` and `traits_confidence` controls.
- Export warnings: several division/location values lacked coordinates or Auspice metadata matches; expected for Brazil-plus-global context with raw Pathoplexus geography strings.

## Open Questions

- Provide or approve DENV-1 mutation-based clade definitions for `augur clades`.
- Calibrate reference-specific terminal masking.
