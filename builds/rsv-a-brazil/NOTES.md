# RSV-A Brazil — Build Notes

## Reference
- NC_038235.1 (15,222 bp) — Human respiratory syncytial virus isolate HRSV/A/USA/001/198X
- ViralQC dataset: auto-selected by BLAST (`rsv-a` Nextclade dataset used)

## Data
- Source: Pathoplexus (organism: rsv-a, OPEN data only)
- Total available: ~52,000 globally (40,722 OPEN); ~13,783 pass QC (genome_quality A/B)

## Status
- [x] Ingest dry-run (integration test)
- [x] Live ingest
- [x] Live phylo / end-to-end

## Open Questions
- Terminal BED: `masks/reference_terminal.bed` generated from NC_038235.1 UTR annotations; review/calibrate before production use.
- Clade definitions for RSV-A WHO nomenclature (e.g. A.D.1) — header-only placeholder for now.

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 40,722 fetched (OPEN), 13,783 QC-passed (genome_quality A/B, coverage ≥0.7), 977 subsampled
- **Fixes applied**: `expected_virus: rsv_a` now uses the external ViralQC alias registry; subsample.yaml converted from `subsamples:` to `samples:` schema
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 1.2M on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_sites_file: masks/reference_terminal.bed`
