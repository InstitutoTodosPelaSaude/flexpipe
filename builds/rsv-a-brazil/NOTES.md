# RSV-A Brazil — Build Notes

## Reference
- NC_038235.1 (15,222 bp) — Human respiratory syncytial virus isolate HRSV/A/USA/001/198X
- ViralQC dataset: `rsv-a` (expected_virus: "Human orthopneumovirus")

## Data
- Source: Pathoplexus (organism: rsv-a, OPEN data only)
- Total available: ~52,000 globally; ~1,506 Brazil (OPEN)

## Status
- [ ] Ingest dry-run (integration test)
- [ ] Live ingest
- [ ] Live phylo / end-to-end

## Open Questions
- Terminal mask values (mask_5prime, mask_3prime) for NC_038235.1 — not yet calibrated, set to 0.
- ViralQC dataset slug for RSV-A — verify `rsv-a` dataset exists in viralQC datasets.
- Clade definitions for RSV-A WHO nomenclature (e.g. A.D.1) — header-only placeholder for now.

## Run Log
(empty — not yet run)
