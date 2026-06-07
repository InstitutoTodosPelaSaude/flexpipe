# OROV-L Brazil — Build Notes

## Reference
- PP154172.1 (6,814 bp) — Oropouche virus isolate ILMD_TF29 segment L (Tefé outbreak)
- ViralQC dataset: `orov-tefe-l` (auto-selected via BLAST)
- Alternative: NC_005776.1 (RefSeq L segment) → `orov-refseq-l` dataset

## Data
- Source: NCBI (taxid 118655, Oropouche virus)
- Total available: ~983 L segment sequences; ~881 from Brazil

## Status
- [ ] Ingest dry-run (integration test)
- [ ] Live ingest
- [ ] Live phylo / end-to-end

## Open Questions
- ViralQC expected_virus string for Oropouche — verify exact match against ViralQC output
  (`Oropouche orthobunyavirus` or `Oropouche virus`?).
- Terminal mask values (mask_5prime, mask_3prime) for PP154172.1 — not calibrated, set to 0.
- Clade definitions — header-only placeholder; Nextclade provides `clade` from ViralQC.

## Run Log
(empty — not yet run)
