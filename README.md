# flexpipe

A flexible Nextstrain pipeline for genomic epidemiology of viral pathogens. Supports data ingestion from [Pathoplexus](https://pathoplexus.org/) or [NCBI](https://www.ncbi.nlm.nih.gov/labs/virus/vssi/), optional integration of local surveillance sequences, automated QC via [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC), and a complete phylogenetic workflow ending in an [Auspice](https://auspice.us/)-compatible JSON.

> **Full documentation:** https://flexpipe.readthedocs.io/en/latest/

## Quick Start

### Installation

```bash
git clone --recurse-submodules https://github.com/InstitutoTodosPelaSaude/flexpipe.git
cd flexpipe
conda env create -f config/nextstrain.yml
conda activate nextstrain
pip install -e '.[test,dev]'
bash scripts/install_viralqc.sh
```

### Run

```bash
flexpipe-run \
    --config builds/yfv-brazil/config.yaml \
    --workdir /path/to/workdir/yfv-brazil \
    --run-date 2026-06-06

auspice view --datasetDir /path/to/workdir/yfv-brazil/auspice/
```

Open `http://localhost:4000` in your browser.

---

## Documentation

### Getting Started
- [Installation](https://flexpipe.readthedocs.io/en/latest/installation.html) — detailed setup guide
- [Quickstart](https://flexpipe.readthedocs.io/en/latest/quickstart.html) — minimal end-to-end run
- [Tutorial](https://flexpipe.readthedocs.io/en/latest/tutorial/index.html) — guided walkthrough

### Reference
- [Architecture](https://flexpipe.readthedocs.io/en/latest/architecture.html) — two-stage design, workdir isolation
- [Configuration](https://flexpipe.readthedocs.io/en/latest/configuration.html) — all config keys and options
- [Pipeline](https://flexpipe.readthedocs.io/en/latest/pipeline/overview.html) — ingest and phylogenetic stages
- [Commands](https://flexpipe.readthedocs.io/en/latest/commands.html) — all console scripts
- [Builds](https://flexpipe.readthedocs.io/en/latest/builds/overview.html) — per-pathogen configuration
- [Troubleshooting](https://flexpipe.readthedocs.io/en/latest/troubleshooting.html) — common issues and fixes

### Development
- [Developer Guide](https://flexpipe.readthedocs.io/en/latest/developer-guide.html) — testing, linting, documentation
- [Citation](https://flexpipe.readthedocs.io/en/latest/citation.html) — how to cite flexpipe and upstream tools

---

## Example Builds

flexpipe includes 15 production-ready and template builds:

- **Yellow Fever Virus (YFV) Brazil** — Pathoplexus source, production-tuned
- **Dengue Virus 1–4 Brazil** — Pathoplexus source, single-serotype examples
- **Zika Virus Brazil** — NCBI source (template for NCBI-based builds)
- **RSV-A/B Brazil, RSV-A Global** — Pathoplexus source, segmented single-segment workflow
- **Influenza A/B (HA Brazil)** — NCBI source, segment-specific builds
- **Chikungunya, Oropouche** — Additional alphaviruses and bunyaviruses
- **Local Example** — Bring-your-own-data template

See [Builds](https://flexpipe.readthedocs.io/en/latest/builds/example-builds.html) for details.

---

## Features

- **Data ingestion**: Pathoplexus/LAPIS, NCBI Entrez, or local files
- **Quality control**: ViralQC (BLAST + Nextclade) with genome quality grades and clade assignment
- **Curation**: Automated metadata normalization, region/lineage assignment, deduplication
- **Subsampling**: Balanced stratification by geography and time
- **Phylogenetics**: MAFFT alignment, IQ-TREE 3 tree building, TreeTime temporal calibration
- **Visualization**: Auspice-ready JSON with colorings, filters, geographic maps

---

## Requirements

- Linux or macOS
- Conda (Miniforge, Mambaforge, or Anaconda)
- ~8 GB disk space (for ViralQC datasets)
- ~10 minutes for first pipeline run (on 4 CPU cores)

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Contributing

For bugs, feature requests, or contributions, open an issue or pull request on [GitHub](https://github.com/InstitutoTodosPelaSaude/flexpipe).

## References

flexpipe builds on:
- [Nextstrain/Augur](https://docs.nextstrain.org/projects/augur/) — phylogenetic framework
- [IQ-TREE 3](http://www.iqtree.org/) — maximum-likelihood tree building
- [MAFFT](https://mafft.cbrc.jp/alignment/software/) — sequence alignment
- [TreeTime](https://github.com/neherlab/treetime) — temporal phylogenetics
- [Nextclade](https://docs.nextstrain.org/projects/nextclade/) — viral clade assignment
- [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC) — genome quality control
