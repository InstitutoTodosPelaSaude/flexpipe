# ZIKV Brazil — Build Notes

## Reference
- NC_035889.1 (10,808 bp) — Zika virus isolate ZIKV/H. sapiens/Brazil/Natal/2015
- ViralQC dataset: `zikav` (community/itps/zikav)

## Status
- [x] Ingest dry-run (integration test) — OK via `pytest -m integration`
- [x] Live ingest — OK 2026-06-07
- [x] Live phylo / end-to-end — OK 2026-06-07

## Open Questions
- Terminal mask values (mask_5prime, mask_3prime) for NC_035889.1 — not yet calibrated, set to 0.

## Run Log

### 2026-06-07 — First live run (NCBI, Brazil-focal)

**Ingest:**
- Source: NCBI (taxid 64320, genome_size 10808)
- Merged: 1,734 records
- Curated: 1,277 records (after QC filters)
- Subsampled: 339 records
- INSDC pipeline fix applied: 25 synthetic-construct records had `missing: synthetic construct` in
  `collection_date`; normalized to empty by `_normalize_insdc()` before `augur curate format-dates`.
- Exit code: 0

**Phylo (first-pass profile: JC, no support, no confidence):**
- Tree: IQ-TREE 3, JC model, no UFBoot
- Auspice JSON: `/tmp/flexpipe-runs/zikv-brazil/auspice/results.json` (2.5 MB)
- Exit code: 0

**Remaining gaps:** clade TSV header-only (ViralQC Nextclade provides `clade`); terminal masks
uncalibrated; no mutation-based clade definitions yet.
