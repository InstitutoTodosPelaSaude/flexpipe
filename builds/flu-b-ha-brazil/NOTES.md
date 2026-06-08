# flu-b-ha-brazil — Build Notes

## Reference
- KX058884.1 (1,885 bp) — B/Brisbane/60/2008 Victoria lineage HA
- ViralQC dataset: flu-b-ha (via BLAST auto-select)
- Yamagata lineage is effectively eliminated post-2020; this build targets Victoria only.

## Data
- Source: NCBI (taxid 11520, Influenza B virus); requires NCBI_EMAIL env var
- expected_segment: "" — ViralQC uses "HA" not "4"; Nextclade QC filters non-HA by alignment quality
- expected_virus: "" — flu strain names in blast.tsv are strain-specific

## Status
- [x] Ingest dry-run (integration test)
- [x] Live ingest
- [x] Live phylo / end-to-end

## Open Questions
- Terminal mask values not calibrated (set to 0).
- Clade definitions — header-only placeholder; Nextclade provides clade from ViralQC.

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 80,048 fetched, 79,907 QC-passed (genome_quality A/B), 319 subsampled
- **Fixes applied**: expected_segment="" (ViralQC uses "HA" not "4"; flu B uses segment name strings not numbers)
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 1.6M on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_5prime: 0`, `mask_3prime: 0`
- **Exit code**: 0 (ingest + phylo)
