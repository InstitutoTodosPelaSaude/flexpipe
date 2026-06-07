# flu-h1n1-ha-brazil — Build Notes

## Reference
- MW626062.1 (1,752 bp) — A/Wisconsin/588/2019(H1N1) HA gene
- ViralQC dataset: flu-h1n1-ha-MW626062 (via BLAST auto-select)
- Alternative: flu-h1n1-ha-CY121680 (A/California/07/2009 prototype).

## Data
- Source: NCBI (taxid 114727 (H1N1 subtype))
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
