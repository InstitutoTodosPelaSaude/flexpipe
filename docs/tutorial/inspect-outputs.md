# Inspect Outputs

Understand flexpipe's outputs and dig deeper into results.

## Time Estimate

~10 minutes

## Your Variables

```bash
export WORKDIR=/tmp/yfv-tutorial
```

(From [First Run](first-run.md))

## Key Output Files

### Auspice JSON

```bash
ls -lh $WORKDIR/auspice/results.json
```

This is the main output. Open it in Auspice:

```bash
auspice view --datasetDir $WORKDIR/auspice/
```

The JSON contains:
- Phylogenetic tree (time-calibrated)
- Metadata (strain, date, region, etc.)
- Mutations and traits
- Color scheme

### QC Summary

QC statistics from the ingest stage:

```bash
cat $WORKDIR/results/ingest/qc_summary.tsv
```

Example output:
```
attribute	value
input_sequences	500
sequences_after_qc	480
genome_quality_a_count	300
genome_quality_b_count	180
min_sequences_check	pass
```

This tells you how many sequences passed each filter.

### Subsampled Metadata

The metadata fed to phylogenetics:

```bash
head $WORKDIR/results/subsampled/metadata.tsv
```

Columns include:
- `strain` — sequence ID
- `date` — collection date (YYYY-MM-DD)
- `country`, `division`, `location` — geography
- `region` — macro-region (continent or Brazil state)
- `genome_quality` — ViralQC grade (A, B, C, D)
- `coverage` — aligned fraction
- `clade_truncated` — hierarchical clade

Use this to understand what sequences made it into the tree.

### Filter Log

Sequences excluded by QC:

```bash
head $WORKDIR/results/ingest/filter_log.tsv
```

Example:
```
strain	filter_value	filter_type
BAD_SEQ_001	C	genome_quality
BAD_SEQ_002	0.5	min_coverage
```

Shows why each sequence was excluded.

### Manifest

Run provenance and configuration fingerprint:

```bash
cat $WORKDIR/manifest.json | python -m json.tool | head -20
```

Example:
```json
{
  "workflow": "flexpipe",
  "version": "0.2.0",
  "run_id": "abc123...",
  "config_hash": "sha256-...",
  "data_source": "pathoplexus",
  "run_date": "2025-06-01",
  "stages_completed": ["ingest", "phylo"]
}
```

The `config_hash` is identical if you re-run with the same config and `--run-date`.

---

## Exploring in Auspice

### Apply Filters

Right sidebar → click "Filters". Select a region or country to highlight sequences.

### View Mutations

Hover over branches to see defining mutations (nucleotide + amino acid).

### Inspect Metadata

Click a strain in the tree. A panel shows its metadata:
- Collection date
- Geographic location
- Genome quality
- Clade
- etc.

### Color Schemes

The tree is colored by the `colours` config (default: region). Change coloring in the Auspice sidebar (Color By dropdown).

### Export Subtrees

Select a clade, right-click, "Export subtree as FASTA" to get sequences from that branch.

---

## Advanced: Coordinate Cache

The coordinate cache speeds up future geocoding:

```bash
cat $WORKDIR/cache/cache_coordinates.tsv | head
```

Example:
```
name	latitude	longitude
Brazil	-14.2	-51.9
SP	-23.5	-46.6
```

To share this cache across runs, set:

```yaml
coordinates:
  shared_cache: /path/to/shared_cache.tsv
```

Then subsequent runs will reuse cached coordinates instead of querying Nominatim.

---

## Troubleshooting

### Empty results.json

Check that phylogenetics completed:

```bash
ls -lh $WORKDIR/logs/phylo.log
```

If missing, check `logs/ingest.log` for errors.

### Wrong number of sequences in tree

Check the QC summary and filter log:

```bash
cat $WORKDIR/results/ingest/qc_summary.tsv
```

If too few sequences passed QC, adjust `qc.genome_quality` or `qc.min_coverage` in config.

### Coordinates missing from map

Check the latlongs file:

```bash
wc -l $WORKDIR/config/latlongs.tsv
```

If empty or sparse, geocoding may have failed. Check:

```bash
tail $WORKDIR/logs/ingest.log | grep -i nominatim
```

---

## Summary

You've now:
1. ✓ Run the full pipeline
2. ✓ Modified configuration
3. ✓ Set up a new pathogen
4. ✓ Analyzed local data
5. ✓ Inspected results

You're ready to use flexpipe for your own analyses! See [Configuration Reference](../configuration.md) and [Troubleshooting](../troubleshooting.md) for further guidance.
