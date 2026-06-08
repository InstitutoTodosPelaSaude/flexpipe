# flu-h3n2-ha-brazil — Build Notes

## Reference
- CY163680.1 (1,737 bp) — A/Wisconsin/67/2005(H3N2) HA gene
- ViralQC dataset: flu-h3n2-ha-CY163680 (via BLAST auto-select)
- Alternative: flu-h3n2-ha-EPI1857216 (A/Darwin/6/2021, more recent; may not be in local ViralQC install)

## Data
- Source: NCBI (taxid 119210, H3N2 subtype); requires NCBI_EMAIL env var
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
- **Ingest**: 61,601 fetched, 59,356 QC-passed (genome_quality A/B), 252 subsampled
- **Fixes applied**: expected_segment="" (ViralQC uses "HA" not "4"); 183 MM/DD/YYYY dates converted to ISO; `--failure-reporting warn` added to format-dates
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 1.5M on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_5prime: 0`, `mask_3prime: 0`
- **Exit code**: 0 (ingest + phylo)
