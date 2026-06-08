# Quickstart

Run a complete flexpipe analysis end-to-end in minutes. This example uses the Yellow Fever Virus (YFV) Brazil build.

## Prerequisites

- flexpipe installed (see [Installation](installation.md))
- ~1 GB disk space for results
- ~5 minutes (ingest + phylogenetics on 4 cores)

## Run the Pipeline

```bash
flexpipe-run \
    --config builds/yfv-brazil/config.yaml \
    --workdir /tmp/yfv-demo \
    --run-date 2026-01-01 \
    --cores 4
```

The `--run-date` flag controls the analysis window for subsampling. Sequences collected after this date are excluded.

## What Happened

The pipeline completed two stages:

- **Ingest**: fetched ~500 YFV sequences from Pathoplexus, performed quality control, and subsampled to ~100 representative strains
- **Phylogenetics**: aligned sequences, built a phylogenetic tree, calibrated it in time, and exported results for visualization

Results are in `/tmp/yfv-demo/auspice/results.json`.

## Visualize

Open the Auspice viewer:

```bash
auspice view --datasetDir /tmp/yfv-demo/auspice/
# Open http://localhost:4000 in your browser
```

You should see an interactive phylogenetic tree with geographic and temporal context.

## Next Steps

- Modify parameters in `builds/yfv-brazil/config.yaml` and re-run
- Follow the [Tutorial](tutorial/index.md) for guided walkthrough of all features
- See [Configuration Reference](configuration.md) for all available options
