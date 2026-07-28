# Adding a New Pathogen

This guide walks you through adding a new viral pathogen build to flexpipe. The process involves copying a template, configuring data sources, setting up phylogenetic parameters, and registering integration tests.

## Prerequisites

- A reference genome (GenBank format, `.gb`)
- Access to sequence data (Pathoplexus, NCBI, or local file)
- ~1 hour for setup + testing

## Step-by-Step Setup

### 1. Copy Template Build

Start with an existing build as a template:

```bash
cp -r builds/yfv-brazil builds/my-pathogen
cd builds/my-pathogen
```

Choose a template based on your data source:
- **NCBI data**: use `builds/zikv-brazil/` (NCBI example)
- **Pathoplexus data**: use `builds/denv3-brazil/` or `builds/rsv-a-brazil/`
- **Single-segment** (flu HA, RSV L, etc.): use `builds/flu-h1n1-ha-brazil/` or `builds/orov-l-brazil/`

### 2. Update config.yaml

Edit `config.yaml` with your pathogen-specific settings:

#### Data Source

```yaml
data_source: ncbi  # or: pathoplexus, local
region_source: country  # or: division (Brazil-only)
```

#### Reference Genome

```yaml
files:
  reference: "reference.gb"
  reference_name: "NC_XXXXXX.1"
  clades: "clades.tsv"
```

Replace with your actual GenBank accession.

#### Phylogenetic Parameters

```yaml
parameters:
  mask_5prime: 0  # or: reference-specific value (UTR length)
  mask_3prime: 0  # or: reference-specific value
  ufboot: 0  # First-pass: 0 (disabled); Production: 1000
  model: "JC"  # First-pass; Production: "MFP"
  root: "least-squares"
  coalescent: "skyline"
```

```{warning}
**Terminal masking is per-reference.** For a new reference:
1. Use `flexpipe-reference-mask` to generate suggested values
2. Review the output (UTR detection may need tweaking)
3. Set `parameters.mask_5prime` and `mask_3prime` accordingly
```

#### NCBI Configuration

```yaml
ncbi:
  taxid: 11292  # Your NCBI taxonomy ID
  genome_size: 10000  # Approximate size in bp
  min_length: 8000
  max_length: 12000
  email: ""  # Use NCBI_EMAIL env var
  api_key: ""  # Use NCBI_API_KEY env var (optional)
```

Find your taxid: [NCBI Taxonomy](https://www.ncbi.nlm.nih.gov/taxonomy)

> **Influenza A caveat:** do not use the subtype-level taxids (`114727` for H1N1, `119210` for
> H3N2). NCBI no longer assigns recent submissions to them, so a subtype-taxid fetch silently
> stops around 2018 and misses all contemporary sequences. Instead use the generic *Influenza A
> virus* taxon `taxid: 11320` with an `extra_search_term` to scope to the subtype, and let ViralQC
> identify the segment/subtype/clade:
>
> ```yaml
> ncbi:
>   taxid: 11320
>   extra_search_term: "AND H1N1[All Fields]"   # or "AND H3N2[All Fields]"
> viralqc:
>   expected_segment: "ha"
>   clade_column: "legacy-clade"
> ```
>
> A build whose sampling inexplicably cuts off around 2018 with no recent tips is the tell-tale
> sign of the subtype-taxid trap.

#### Pathoplexus Configuration

```yaml
pathoplexus:
  organism: "Dengue virus 3"
  base_url: "https://lapis.cov-spectrum.org"
  query_params:
    dataUseTerms: OPEN
  strip_fasta_id_suffix: true  # Remove |EPI_ISL_... if present
```

#### ViralQC Configuration

```yaml
viralqc:
  expected_virus: "dengue"  # Alias-aware key
  expected_segment: "genome"
  clade_column: "clade"     # ViralQC results.tsv column mapped to `clade`
  mode: "run"  # or: precomputed, skip
```

Check available viruses:
```bash
vqc --list-viruses
```

If your virus isn't listed or has a different name, create/update aliases (see [ViralQC Integration](../viralqc-integration.md)).

Set `clade_column` per virus: `legacy-clade` for seasonal influenza A HA and per-lineage flu-B
Victoria (default `clade` is now a sparse subclade system and returns mostly `unassigned`),
`legacy-clade-vic` for the combined flu-B dataset, `legacy_clade` (underscore) for hMPV; keep the
default `clade` for measles, RSV, dengue, YFV, Zika, mumps, and SARS-CoV-2. See
[Clade Column Selection](../viralqc-integration.md#clade-column-selection).

#### Curation

```yaml
curation:
  clade_levels: 1  # Hierarchy depth for clade_truncated
  lineage_parser: "none"  # or: dengue, pango, generic_dot
  lineage_columns: []  # Derived columns (if parser != none)
```

#### QC Thresholds

```yaml
qc:
  genome_quality: [A, B]
  min_coverage: 0.70
  min_sequences: 10  # Minimum output sequences (error if below)
```

### 3. Add Reference Genome

Replace `reference.gb` with your actual reference:

```bash
# Download from NCBI
wget https://www.ncbi.nlm.nih.gov/nuccore/NC_XXXXXX.1?report=fasta_cds_faa&rettype=gb&retmode=txt \
  -O reference.gb

# Or use a local file
cp /path/to/reference.gb reference.gb
```

Verify the file is valid GenBank:
```bash
grep "^ORIGIN" reference.gb
```

### 4. Create Clade Definitions

Create `clades.tsv` with mutation-based clade definitions:

```
clade	gene	site	alt
Clade_A	ORF1ab	100	T
Clade_A	E	501	Y
Clade_B	ORF1ab	100	A
Clade_B	E	501	D
```

Or start with a header-only file (no clades):
```
clade	gene	site	alt
```

### 5. Configure Subsampling

Edit `subsample.yaml`:

```yaml
samples:
  group_by:
    - division  # or: country, year, etc.
    - year
  sequences_per_group: 5

include:
  - strains: keep.txt

exclude:
  - strains: ignore.txt

defaults:
  max_date: 2025-12-31
```

Create `keep.txt` and `ignore.txt` (can be empty):
```bash
touch keep.txt ignore.txt
```

### 6. Set Up Auspice Configuration

Edit `auspice_config.json`:

```json
{
  "title": "My Pathogen (Region)",
  "description": "Real-time tracking of My Pathogen",
  "colorings": [
    {"key": "region", "title": "Region", "type": "categorical"},
    {"key": "country", "title": "Country", "type": "categorical"}
  ],
  "filters": ["region", "country"],
  "panels": ["tree", "map"]
}
```

Adjust colorings and filters to match your metadata fields.

### 7. Update ignore.txt (Data Source-Specific)

#### NCBI

Always exclude the reference accession (else it appears as a sequence):

```bash
echo "NC_XXXXXX.1" > ignore.txt
```

#### Pathoplexus

Usually no strain-level filtering needed; use `query_params` to filter by data use terms, date, region.

#### Local

Add problematic sequences to ignore.txt if found during testing.

### 8. Validate the Build

Check for configuration errors:

```bash
flexpipe-validate-build builds/my-pathogen/config.yaml
```

Should report: `Config validation passed.`

### 9. Test with `--stage ingest`

Run ingest only to verify data fetching and QC:

```bash
flexpipe-run \
  --config builds/my-pathogen/config.yaml \
  --workdir /tmp/my-pathogen-test \
  --stage ingest \
  --run-date 2025-06-01
```

Check outputs:
- `<workdir>/results/subsampled/metadata.tsv` — must have rows
- `<workdir>/results/ingest/qc_summary.tsv` — check counts

If ingest fails, check:
- Data source credentials (`NCBI_EMAIL`, `PPX_AUTH_TOKEN`)
- ViralQC alias mapping (unexpected virus/segment labels)
- Metadata format (Pathoplexus columns required)

### 10. Test Full Pipeline

Run the complete pipeline:

```bash
flexpipe-run \
  --config builds/my-pathogen/config.yaml \
  --workdir /tmp/my-pathogen-full \
  --run-date 2025-06-01 \
  --cores 4
```

Visualize:
```bash
auspice view --datasetDir /tmp/my-pathogen-full/auspice/
```

Open `http://localhost:4000` and inspect the tree, map, colorings, and filters.

### 11. Register Integration Tests (Optional)

To include your build in automated testing, edit `tests/integration/conftest.py`:

```python
builds_to_test = [
    "yfv-brazil",
    "denv3-brazil",
    "my-pathogen",  # Add your build
]
```

Then run integration tests:

```bash
pytest -m integration -k "my-pathogen"
```

## Single-Segment Special Cases

If your pathogen has multiple segments (flu, RSV, etc.):

1. **Create separate builds per segment**:
   - `builds/flu-h1n1-ha-brazil/`
   - `builds/flu-h1n1-na-brazil/`

2. **Set segment in config**:
   ```yaml
   viralqc:
     expected_segment: "ha"
   ```

3. **Reference and masks are segment-specific**: YFV uses full genome; flu uses HA sequence only.

## Geographic Constraints (Brazil vs Global)

### Brazil-Specific Build

```yaml
region_source: division  # States → macro-regions
colours:
  - continent
  - country
  - division
  - location
```

### Global Build

```yaml
region_source: country  # Countries → continents
colours:
  - continent
  - country
  - location
```

## Fragment / Gene Window Builds

When most sequences are partial (gene-length) or your analysis targets a specific
marker window (e.g. measles N450, flu HA1, RSV F), use fragment mode.

### When to choose fragment mode

- Standard genotyping marker is a **sub-genomic window** (450 nt, 1 kb, etc.)
- Most sequences in the database cover the gene only, not the full genome
- You want QC gated on the **gene's** coverage/quality, not whole-genome coverage

### Prerequisites

Fragment mode requires a Nextclade dataset that declares a `target_gene` for your
virus.  Check the ViralQC registry:

```bash
cat viralQC/viralqc/config/datasets.yml | grep -A3 "target_gene"
```

If no dataset exists, use `viralqc.mode: skip` (whole-genome mode only).

### Step-by-step: adding a fragment build

**1. Produce the gene-only reference:**

```bash
flexpipe-reference-slice \
    --reference  builds/measles-b3-global/reference.gb \
    --region     1233..1682 \
    --gene       N  --feature-type CDS \
    --new-id     NC_001498.1 \
    --output-reference  builds/my-fragment-build/reference.gb \
    --output-bed        builds/my-fragment-build/masks/reference_terminal.bed
```

For a tight coding window the BED will be empty — commit it anyway (the pipeline
reads it unconditionally when `mask_sites_file` points to it).

**2. Set `mode: fragment` in `config.yaml`:**

```yaml
mode: "fragment"

fragment:
  target_gene: "N"           # matches ViralQC dataset target_gene
  min_target_coverage: 0.70
  target_quality: ["A", "B"]

viralqc:
  mode: "run"          # fragment requires run — skip/precomputed forbidden
  expected_virus: "measles"

parameters:
  mask_5prime: 0         # gene window has no UTR flanks
  mask_3prime: 0
  mask_sites_file: "builds/my-fragment-build/masks/reference_terminal.bed"
```

**3. Coordinate system:** all coordinates in `clades.tsv` must be **gene-relative**
(position 1 = first base of the sliced window).

**4. Validate:**

```bash
flexpipe-validate-build builds/my-fragment-build/config.yaml
# ✓  mode=fragment: target_gene='N' set
# ✓  Dataset found: measles-N450-WHO-2012 (target_gene=N, virus=measles)
```

Use `builds/measles-b3-n450-global/` as a worked reference example.  See
[Fragment Analysis](../pipeline/fragment-analysis.md) for the full guide.

## Checklist

- [ ] `config.yaml` updated with correct data source, reference, parameters
- [ ] Reference genome `.gb` file present and valid
- [ ] `clades.tsv` populated (or header-only if no clades)
- [ ] `subsample.yaml` stratification makes sense for your data
- [ ] `auspice_config.json` colorings match metadata columns
- [ ] `keep.txt` and `ignore.txt` created (can be empty)
- [ ] `flexpipe-validate-build` passes
- [ ] Ingest completes: `results/subsampled/metadata.tsv` has rows
- [ ] Full pipeline completes without errors
- [ ] Auspice visualization displays tree, map, and metadata
- [ ] (Optional) Integration tests registered in `conftest.py`

## Troubleshooting

See [Troubleshooting](../troubleshooting.md) for common issues and solutions.
