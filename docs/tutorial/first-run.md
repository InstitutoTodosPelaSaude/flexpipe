# First Run

Your first complete flexpipe analysis: Yellow Fever Virus (YFV) Brazil.

## Time Estimate

~10 minutes (ingest + phylo on 4 cores)

## Setup Variables

Define shell variables for the tutorial. **Copy and run this block** (updates in later chapters):

```bash
export WORKDIR=/tmp/yfv-tutorial
export RUN_DATE=2025-06-01
export CORES=4
```

Verify:
```bash
echo "WORKDIR=$WORKDIR, RUN_DATE=$RUN_DATE, CORES=$CORES"
```

## Run the Pipeline

From the flexpipe repo root, run:

```bash
flexpipe-run \
  --config builds/yfv-brazil/config.yaml \
  --workdir $WORKDIR \
  --run-date $RUN_DATE \
  --cores $CORES
```

This fetches ~500 YFV sequences from Pathoplexus, performs QC, subsamples to ~100 representative strains, builds a phylogenetic tree, and calibrates it in time.

### Expected Output

As the pipeline runs, you'll see Snakemake log messages. After ingest completes (2–5 minutes), phylogenetics begins. Total time: ~10 minutes on 4 cores.

When done, you'll see:
```
[snakemake] Finished job X.
[snakemake] X of X steps (100%) done.
```

## What Happened: Ingest Stage

1. **Fetched** ~500 YFV sequences from Pathoplexus
2. **QC'd** with ViralQC (BLAST + Nextclade; genome_quality grades A–D)
3. **Curated** metadata (normalized dates, assigned regions, parsed clades)
4. **Filtered** by genome quality (grades A–B only)
5. **Subsampled** by division (state) and year (5 per group) → ~100 sequences
6. **Colored** and **geocoded** for visualization

Output: `$WORKDIR/results/subsampled/{metadata.tsv, sequences.fasta}`

## What Happened: Phylogenetic Stage

1. **Aligned** subsampled sequences to YFV reference (MAFFT)
2. **Masked** terminal regions (UTRs; per-reference)
3. **Built tree** with IQ-TREE 3 (JC model, no UFBoot for speed)
4. **Refined** with TreeTime (temporal calibration)
5. **Inferred** amino acid mutations, geographic traits, and clades
6. **Exported** to Auspice JSON

Output: `$WORKDIR/auspice/results.json`

## Check Results

### Verify Files Exist

```bash
ls -lh $WORKDIR/results/subsampled/metadata.tsv
ls -lh $WORKDIR/auspice/results.json
```

Both should exist (metadata.tsv: ~50 KB, results.json: ~2–5 MB).

### Count Sequences

```bash
wc -l $WORKDIR/results/subsampled/metadata.tsv
```

Should be ~101 (100 sequences + header).

### Check QC Summary

```bash
cat $WORKDIR/results/ingest/qc_summary.tsv
```

Shows genome quality grades, coverage, etc. for filtered sequences.

## Visualize

Open the results in Auspice:

```bash
auspice view --datasetDir $WORKDIR/auspice/
```

Then open `http://localhost:4000` in your browser.

You should see:
- Interactive phylogenetic tree (left)
- Geographic map (top right)
- Metadata panels (right sidebar)
- Color scheme applied (by region or country)

### Explore the Tree

- **Zoom** with scroll wheel or pinch
- **Pan** by dragging
- **Click strains** to see metadata
- **Use filters** (right sidebar) to highlight sequences
- **View mutations** by hovering over branches

## Stage-by-Stage Runs (Optional)

To understand the pipeline better, run stages separately:

### Ingest Only

```bash
flexpipe-run \
  --config builds/yfv-brazil/config.yaml \
  --workdir $WORKDIR \
  --stage ingest \
  --run-date $RUN_DATE
```

This stops after subsampling. Check:
```bash
ls $WORKDIR/results/subsampled/
```

### Phylo Only

```bash
flexpipe-run \
  --config builds/yfv-brazil/config.yaml \
  --workdir $WORKDIR \
  --stage phylo
```

This skips ingest and uses existing subsampled data. Check:
```bash
ls $WORKDIR/auspice/results.json
```

## Next Step

Proceed to [Config Walkthrough](config-walkthrough.md) to modify pipeline parameters and see how results change.
