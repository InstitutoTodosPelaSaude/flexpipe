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
- [ ] Live phylo / end-to-end (running as of 2026-06-07)

## Open Questions
- Terminal mask values (mask_5prime, mask_3prime) for NC_038235.1 — not yet calibrated, set to 0.
- Clade definitions for RSV-A WHO nomenclature (e.g. A.D.1) — header-only placeholder for now.

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 40,722 fetched (OPEN), 13,783 QC-passed (genome_quality A/B, coverage ≥0.7), 977 subsampled
- **Fixes applied**: expected_virus set to "" (ViralQC results.tsv uses Nextclade naming, not blast.tsv); subsample.yaml converted from `subsamples:` to `samples:` schema
- **Phylo**: IQ-TREE3 JC model running as of 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_5prime: 0`, `mask_3prime: 0`
