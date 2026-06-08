# flu-h1n1-ha-brazil — Build Notes

## Reference
- MW626062.1 (1,752 bp) — A/Wisconsin/588/2019(H1N1) HA gene
- ViralQC dataset: flu-h1n1-ha-MW626062 (via BLAST auto-select)
- Alternative: flu-h1n1-ha-CY121680 (A/California/07/2009 prototype)

## Data
- Source: NCBI (taxid 114727, H1N1 subtype); requires NCBI_EMAIL env var
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
- **Ingest**: 64,869 fetched, 49,706 QC-passed (genome_quality A/B), 424 subsampled
- **Fixes applied**: expected_segment="" (ViralQC uses "HA" not "4"); "unknown" dates normalized; MM/DD/YYYY dates patched; `--failure-reporting warn` added to format-dates
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 2.0M on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_5prime: 0`, `mask_3prime: 0`
- **Exit code**: 0 (ingest + phylo)
