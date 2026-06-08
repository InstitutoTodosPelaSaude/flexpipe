# OROV-L Brazil — Build Notes

## Reference
- PP154172.1 (6,814 bp) — Oropouche virus isolate ILMD_TF29 segment L (Tefé outbreak)
- ViralQC dataset: `orov-tefe-l` (auto-selected via BLAST)
- Alternative: NC_005776.1 (RefSeq L segment) → `orov-refseq-l` dataset

## Data
- Source: NCBI (taxid 118655, Oropouche virus); requires NCBI_EMAIL env var
- Total available: ~902 L segment sequences; 827 pass QC

## Status
- [x] Ingest dry-run (integration test)
- [x] Live ingest
- [x] Live phylo / end-to-end

## Open Questions
- Terminal mask values (mask_5prime, mask_3prime) for PP154172.1 — not calibrated, set to 0.
- Clade definitions — header-only placeholder; Nextclade provides `clade` from ViralQC.

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 902 fetched, 827 QC-passed, 128 subsampled
- **expected_virus**: "Oropouche virus" confirmed correct from ViralQC blast.tsv
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 520K on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_5prime: 0`, `mask_3prime: 0`
