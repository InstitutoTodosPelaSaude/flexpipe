# flexpipe

A flexible Nextstrain pipeline for genomic epidemiology of viral pathogens. Supports data ingestion from [Pathoplexus](https://pathoplexus.org/) or [NCBI](https://www.ncbi.nlm.nih.gov/labs/virus/vssi/), optional integration of local surveillance sequences, automated QC via [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC), and a complete phylogenetic workflow ending in an [Auspice](https://auspice.us/)-compatible JSON.

This repository includes a working example build for **Yellow Fever Virus (YFV) in Brazil**, covering sequences from 2015 to the present using Pathoplexus as the data source.

---

## Getting Started

### Requirements

- [conda](https://docs.conda.io/) or [mamba](https://mamba.readthedocs.io/)
- A `nextstrain` conda environment with `augur ≥ 13`, `snakemake`, `iqtree3`, and the dependencies listed in `config/nextstrain.yml`
- [ViralQC](https://github.com/InstitutoTodosPelaSaude/viralQC) installed in a separate conda environment (`viralQC`)

### Running the example (YFV Brazil)

The pipeline is split into two independent workflows. Run them in sequence from the repository root:

**Stage 1 — Ingest**
```bash
conda run -n nextstrain snakemake \
    --snakefile ingest/Snakefile \
    --cores 4
```

**Stage 2 — Phylogenetic**
```bash
conda run -n nextstrain snakemake \
    --snakefile phylogenetic/Snakefile \
    --cores 4
```

**Visualise**
```bash
conda run -n nextstrain auspice view --datasetDir auspice/
```

Open `http://localhost:4000` in your browser.

---

## Pipeline Overview

```
fetch_pathoplexus  (or fetch_ncbi)
    └── merge_local_sequences  (optional local sequences + Pathoplexus/NCBI)
            └── viralqc        (BLAST + Nextclade: QC grades + clade assignment)
                    └── curate_qc  (normalisation, dedup, augur filter)
                            └── prepare  (augur subsample)
                                    ├── coordinates  (geocoding → latlongs.tsv)
                                    ├── generate_name2hue  (colour palette)
                                    └── colours  (colour_scheme.tsv)
                                            └── [phylogenetic/Snakefile]
                                                    align → mask → tree → refine
                                                    → ancestral → translate → traits
                                                    → clades → export → auspice/results.json
```

---

## Stage 1 — Ingest

Sequences and metadata are fetched from **Pathoplexus** (default) or **NCBI**, controlled by `data_source` in `config/config.yaml`. Only one source is active per run.

### Example — YFV Brazil

| Parameter | Value |
|-----------|-------|
| `data_source` | `pathoplexus` |
| `pathoplexus.organism` | `yellow-fever` |
| `pathoplexus.min_completeness` | `0.70` |
| `ncbi.taxid` (fallback) | `11089` |
| `ncbi.genome_size` (bp) | `10862` |

Local surveillance sequences (in `data/new_sequences.fasta` + `data/metadata.xlsx`) are merged with remote data via `merge_local_sequences.py`. Set `local_sequences.enabled: true` in `config.yaml` to activate.

---

## Stage 2 — QC and Curation

**ViralQC** (BLAST + Nextclade) assigns genome quality grades (A–D) and clade labels. The `curate.py` script then:

- Renames and standardises metadata fields (`strain`, `date`, `country`, `division`, `location`, `data_use`, `clade`)
- Computes `clade_truncated` by trimming hierarchical clade names to `clade_levels` levels
- Assigns a `region` column from either country names (global builds) or state names (Brazil-only builds — see `region_source` below)
- Marks each sequence with a `source` label (`Pathoplexus`, `NCBI`, or `ITpS`)
- Deduplicates sequences, preferring local ITpS records

**QC filters** applied by `augur filter`:

| Parameter | Value |
|-----------|-------|
| `qc.genome_quality` | `A`, `B` (grades C and D discarded) |
| `qc.min_coverage` | `0.70` |
| Required columns | `strain`, `date`, `country`, `clade` |

### Region mapping

The `region_source` field in `config.yaml` controls how the `region` column is derived:

| `region_source` | Behaviour | Use case |
|----------------|-----------|----------|
| `"country"` | Maps country name → continent via `REGION_MAP` | Global builds |
| `"division"` | Maps Brazilian state → macro-region via `BRAZIL_REGION_MAP` | Brazil-only builds |

Brazilian macro-regions: **Norte**, **Nordeste**, **Centro-Oeste**, **Sudeste**, **Sul**.

The YFV example uses `region_source: "division"` so that `region` represents intra-country geographic structure rather than a continent label.

---

## Stage 3 — Subsampling

Controlled by `config/subsample.yaml`, which is read by `augur subsample`. The YFV Brazil strategy:

```yaml
defaults:
  min_date: 2015

samples:
  focal:
    query: "source == 'ITpS'"       # local sequences always kept in full

  brazil:
    group_by: [division, year]      # subsample by state and year
    sequences_per_group: 10
    exclude_where:
      - "source=ITpS"
      - "division="
      - "date="
```

For global builds (RSV, Flu), replace `division` with `country` and add `clade_truncated` to `group_by` and `exclude_where`.

---

## Stage 4 — Coordinates and Colours

**Coordinates**: `get_coordinates.py` queries Nominatim (OpenStreetMap) to geocode the columns listed in `coordinates.columns` (default: `division location` for the YFV example). Results are cached in `config/cache_coordinates.tsv`; the output `config/latlongs.tsv` is consumed by `augur export`. The script applies Nominatim featuretype hints per level (`division → state`, `location → city`) and writes incrementally after each new find to avoid data loss on interruption.

**Colours**: `generate_name2hue.py` assigns hues from the subsampled metadata. `colour_maker.py` produces `config/colour_scheme.tsv`. Both are configured via `colours` in `config.yaml`:

```yaml
colours:
  clade:    "clade"
  geo:      "region division location"
  source:   "source"
  data_use: "data_use"
```

---

## Stage 5 — Phylogenetic

Run separately after ingest completes (`snakemake --snakefile phylogenetic/Snakefile --cores N`).

Steps: `align` (MAFFT) → `mask` → `tree` (IQ-TREE 3 UFBoot) → `refine` (TreeTime) → `ancestral` → `translate` → `traits` → `clades` → `export` → `auspice/results.json`

### Key phylogenetic parameters — YFV example

| Parameter | Value | Description |
|-----------|-------|-------------|
| `parameters.model` | `MFP` | ModelFinder Plus — auto-selects best substitution model |
| `parameters.ufboot` | `1000` | Ultrafast bootstrap replicates |
| `parameters.root` | `least-squares` | Root method for time-calibrated tree |
| `parameters.coalescent` | `skyline` | Effective population size model in TreeTime |
| `parameters.date_inference` | `marginal` | Marginal date inference for ambiguous dates |
| `parameters.divergence_units` | `mutations` | Branch length units in timetree |
| `parameters.clock_filter_iqd` | `4` | IQD filter for clock outliers |
| `parameters.ancestral_inference` | `joint` | Joint ancestral reconstruction |
| `parameters.mask_5prime` | `142` | Bases masked at 5′ end (X03700.1-specific) |
| `parameters.mask_3prime` | `548` | Bases masked at 3′ end (X03700.1-specific) |
| `options.threads` | `4` | Threads for MAFFT and IQ-TREE |
| `traits.columns` | `division location clade` | Columns for ancestral trait inference |

### Clade annotation

Clade labels on tree branches are defined in `config/clades.tsv` and applied by `augur clades`. For YFV, genotype information is already present in the metadata `clade` field (sourced from Pathoplexus). The `clades.tsv` defines mutation-based branch labels to annotate internal nodes where a genotype lineage originates.

YFV genotypes are single-level (`I`, `II`, `III`…), so `clade_levels: 1` in `config.yaml` keeps `clade_truncated` equal to `clade`.

---

## Adapting to Another Pathogen

To create a new build, copy `config/` and `data/`, then edit `config/config.yaml` and `config/subsample.yaml`. Scripts and Snakefiles are shared and require no modification for supported pathogens.

Key fields to update in `config.yaml`:

| Field | Description |
|-------|-------------|
| `data_source` | `"pathoplexus"` or `"ncbi"` |
| `pathoplexus.organism` | Pathoplexus organism slug (e.g. `rsv-a`, `yellow-fever`) |
| `ncbi.taxid` | NCBI taxonomy ID |
| `ncbi.genome_size` | Reference genome size in bp |
| `parameters.mask_5prime/3prime` | Terminal masking in bp (0 for full-genome builds) |
| `curation.clade_levels` | Hierarchy depth for `clade_truncated` |
| `region_source` | `"country"` for global builds; `"division"` for Brazil-only |
| `viralqc.*` | ViralQC dataset and paths (must be configured per pathogen) |
| `traits.columns` | Columns for ancestral trait reconstruction |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config/config.yaml` | All pipeline parameters |
| `config/subsample.yaml` | Subsampling strategy (read by `augur subsample`) |
| `config/auspice_config.json` | Auspice display settings (colorings, filters, panels) |
| `config/reference.gb` | Reference genome in GenBank format (X03700.1 for YFV) |
| `config/clades.tsv` | Clade definitions for `augur clades` |
| `config/cache_coordinates.tsv` | Geocoding cache (updated incrementally each run) |
| `config/keep.txt` | Strains to always include (one accession per line) |
| `config/ignore.txt` | Strains to always exclude (reference accession goes here) |
| `data/new_sequences.fasta` | Local sequences (used when `local_sequences.enabled: true`) |
| `data/metadata.xlsx` | Local metadata (used when `local_sequences.enabled: true`) |

---

## Scripts

| Script | Role |
|--------|------|
| `fetch_pathoplexus.py` | Downloads metadata + sequences from Pathoplexus/LAPIS |
| `fetch_ncbi.py` | Downloads from NCBI Entrez by taxid |
| `merge_local_sequences.py` | Merges remote data with local surveillance sequences |
| `curate.py` | ViralQC join, region, clade_truncated, source, dedup |
| `get_coordinates.py` | Geocodes locations via Nominatim with rate-limiting and caching |
| `generate_name2hue.py` | Generates colour hue mapping from subsampled metadata |
| `colour_maker.py` | Assigns hex colours per metadata value |
| `name2shape.py` | Assigns shapes for Auspice display |
| `calculate_delta_frequency.py` | Computes clade frequency changes over time |

---

## Authors

**Anderson Brito** — Instituto Todos pela Saúde (ITpS)
✉️ [andersonbrito@itps.org.br](mailto:andersonbrito@itps.org.br)

**Thales Bermann** — Instituto Todos pela Saúde (ITpS)
✉️ [thalesbermann@gmail.com](mailto:thalesbermann@gmail.com)

---

## License

This project is licensed under the [MIT License](LICENSE).
