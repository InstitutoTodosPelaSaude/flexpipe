# flu-h3n2-ha-brazil — Build Notes

## Reference
- CY163680.1 (1,737 bp) — A/Wisconsin/67/2005(H3N2) HA gene
- ViralQC dataset: flu-h3n2-ha-CY163680 (via BLAST auto-select)
- Alternative: flu-h3n2-ha-EPI1857216 (A/Darwin/6/2021, more recent).

## Data
- Source: NCBI (taxid 119210 (H3N2 subtype))
- expected_segment: "4" (HA = segment 4 in NCBI RefSeq flu)
- expected_virus: "" (flu strain names in blast.tsv are strain-specific; not used for filtering)

## Status
- [ ] Ingest dry-run (integration test)
- [ ] Live ingest
- [ ] Live phylo / end-to-end

## Open Questions
- ViralQC dataset choice: confirm reference preference above.
- Terminal mask values not calibrated (set to 0).
- Clade definitions — header-only placeholder; Nextclade provides clade from ViralQC.

## Run Log
(empty — not yet run)
