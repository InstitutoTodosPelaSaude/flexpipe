# flu-h1n1-ha-brazil — Build Notes

## Reference
- MW626062.1 (1,752 bp) — A/Wisconsin/588/2019(H1N1) HA gene
- ViralQC dataset: flu-h1n1-ha-MW626062 (via BLAST auto-select)
- Alternative: flu-h1n1-ha-CY121680 (A/California/07/2009 prototype)

## Data
- Source: NCBI (taxid 114727, H1N1 subtype); requires NCBI_EMAIL env var
- expected_segment: "ha" — alias registry accepts `HA`, `4`, and segment-name variants
- expected_virus: "flu_a_h1n1" — alias registry accepts strain-specific H1N1 ViralQC labels

## Status
- [x] Ingest dry-run (integration test)
- [x] Live ingest
- [x] Live phylo / end-to-end

## Open Questions
- Terminal BED: `masks/reference_terminal.bed` generated from MW626062.1 CDS boundaries; review/calibrate before production use.
- Clade definitions — header-only placeholder; Nextclade provides clade from ViralQC.

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 64,869 fetched, 49,706 QC-passed (genome_quality A/B), 424 subsampled
- **Fixes applied**: alias-backed virus/HA segment matching; "unknown" dates normalized; flexible date normalizer added before Augur date formatting
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 2.0M on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_sites_file: masks/reference_terminal.bed`
- **Exit code**: 0 (ingest + phylo)
