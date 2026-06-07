# flu-b-ha-brazil — Build Notes

## Reference
- KX058884.1 (1,885 bp) — B/Brisbane/60/2008 Victoria lineage HA
- ViralQC dataset: flu-b-ha (via BLAST auto-select); also flu-vic-ha available
- Yamagata lineage is effectively eliminated post-2020; this build targets Victoria only.

## Data
- Source: NCBI (taxid 11520 (Influenza B virus))
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
