# flexpipe Documentation

**flexpipe** is a flexible Nextstrain pipeline for genomic epidemiology of viral pathogens. It supports data ingestion from Pathoplexus, NCBI, or local surveillance sequences; automated quality control via ViralQC (BLAST + Nextclade); and a complete phylogenetic workflow producing Auspice-compatible JSON for visualization.

## Contents

```{toctree}
:caption: Reference
:maxdepth: 2

installation
quickstart
architecture
configuration
pipeline/overview
pipeline/ingest
pipeline/phylogenetics
pipeline/fragment-analysis
pipeline/local-data
builds/overview
builds/adding-a-pathogen
builds/example-builds
commands
outputs
viralqc-integration
subsampling
visualization
troubleshooting
developer-guide
citation
```

```{toctree}
:caption: Tutorial
:maxdepth: 1

tutorial/index
tutorial/setup
tutorial/first-run
tutorial/config-walkthrough
tutorial/add-pathogen
tutorial/local-data
tutorial/inspect-outputs
```

## Quick Links

- [GitHub Repository](https://github.com/InstitutoTodosPelaSaude/flexpipe)
- [Issues/Bugs](https://github.com/InstitutoTodosPelaSaude/flexpipe/issues)
- **License:** MIT
