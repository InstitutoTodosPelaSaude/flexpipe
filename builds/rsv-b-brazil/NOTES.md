# RSV-B Brazil — Build Notes

## Reference
- NC_001781.1 (15,225 bp) — Human orthopneumovirus Subgroup B, complete genome
- ViralQC dataset: auto-selected by BLAST (`rsv-b` Nextclade dataset used)

## Data
- Source: Pathoplexus (organism: rsv-b, OPEN data only)
- Total available: ~30,497 OPEN globally; ~11,630 pass QC (genome_quality A/B)

## Status
- [x] Ingest dry-run (integration test)
- [x] Live ingest
- [x] Live phylo / end-to-end

## Open Questions
- Terminal BED: `masks/reference_terminal.bed` generated from NC_001781.1 UTR annotations; review/calibrate before production use.
- Clade definitions for RSV-B WHO nomenclature — header-only placeholder for now.

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 30,497 fetched (OPEN), 11,630 QC-passed (genome_quality A/B, coverage ≥0.7), 785 subsampled
- **Fixes applied**: `expected_virus: rsv_b` now uses the external ViralQC alias registry; subsample.yaml schema fixed
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 976K on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_sites_file: masks/reference_terminal.bed`
