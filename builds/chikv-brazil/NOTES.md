# CHIKV Brazil — Build Notes

## Reference
- NC_004162.2 (11,826 bp) — Chikungunya virus complete genome
- ViralQC dataset: `chikv` (community/v-gen-lab/chikV/genotypes)

## Status
- [x] Ingest dry-run (integration test)
- [x] Live ingest
- [x] Live phylo / end-to-end

## Open Questions
- Terminal BED: `masks/reference_terminal.bed` generated from NC_004162.2 CDS boundaries; review/calibrate before production use.
- Brazil-only vs Brazil-focal-with-global-context subsampling — defaulting to Brazil-focal.
- sequences_per_group target confirmed at 2 (Brazil) / 1 (context).

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 3,414 merged (NCBI + local), 3,220 QC-passed, 956 subsampled
- **Phylo**: IQ-TREE3 JC model (no UFBoot, ~35 min); augur refine → export; auspice/results.json 1.1 MB
- **Geocoding**: ~25 min (542 unique locations, Nominatim); 186 latlongs cached
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_sites_file: masks/reference_terminal.bed`
- **Exit code**: 0 (ingest + phylo)
