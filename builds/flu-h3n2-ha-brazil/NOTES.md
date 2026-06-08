# flu-h3n2-ha-brazil — Build Notes

## Reference
- CY163680.1 (1,737 bp) — A/Wisconsin/67/2005(H3N2) HA gene
- ViralQC dataset: flu-h3n2-ha-CY163680 (via BLAST auto-select)
- Alternative: flu-h3n2-ha-EPI1857216 (A/Darwin/6/2021, more recent; may not be in local ViralQC install)

## Data
- Source: NCBI (taxid 119210, H3N2 subtype); requires NCBI_EMAIL env var
- expected_segment: "ha" — alias registry accepts `HA`, `4`, and segment-name variants
- expected_virus: "flu_a_h3n2" — alias registry accepts strain-specific H3N2 ViralQC labels

## Status
- [x] Ingest dry-run (integration test)
- [x] Live ingest
- [x] Live phylo / end-to-end

## Open Questions
- Terminal BED: `masks/reference_terminal.bed` generated from CY163680.1 CDS boundaries; review/calibrate before production use.
- Clade definitions — header-only placeholder; Nextclade provides clade from ViralQC.

## Run Log
### 2026-06-07 — First live run
- **Ingest**: 61,601 fetched, 59,356 QC-passed (genome_quality A/B), 252 subsampled
- **Fixes applied**: alias-backed virus/HA segment matching; flexible date normalizer handles MM/DD/YYYY before Augur date formatting
- **Phylo**: IQ-TREE3 JC model; auspice/results.json 1.5M on 2026-06-07
- **Config**: `model: JC`, `ufboot: 0`, `date_confidence: false`, `traits_confidence: false`, `mask_sites_file: masks/reference_terminal.bed`
- **Exit code**: 0 (ingest + phylo)
