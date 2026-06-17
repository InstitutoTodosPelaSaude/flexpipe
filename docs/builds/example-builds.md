# Example Builds

flexpipe includes 16 example builds covering a range of viral pathogens and data sources. Each build is production-ready or template-quality.

## All Builds

| Build | Pathogen | Data Source | Region | Mode | Focus |
|-------|----------|-------------|--------|------|-------|
| `yfv-brazil` | Yellow Fever Virus | Pathoplexus | Brazil | whole-genome | Production-tuned reference |
| `denv1-brazil` | Dengue Virus 1 | Pathoplexus | Brazil | whole-genome | DENV serotype 1 |
| `denv2-brazil` | Dengue Virus 2 | Pathoplexus | Brazil | whole-genome | DENV serotype 2 |
| `denv3-brazil` | Dengue Virus 3 | Pathoplexus | Brazil | whole-genome | DENV serotype 3 (Track B template) |
| `denv4-brazil` | Dengue Virus 4 | Pathoplexus | Brazil | whole-genome | DENV serotype 4 |
| `zikv-brazil` | Zika Virus | NCBI | Brazil | whole-genome | NCBI data source template |
| `chikv-brazil` | Chikungunya Virus | Pathoplexus | Brazil | whole-genome | Alphaviruses |
| `rsv-a-brazil` | RSV A | Pathoplexus | Brazil | whole-genome | RSV serotype A |
| `rsv-b-brazil` | RSV B | Pathoplexus | Brazil | whole-genome | RSV serotype B |
| `rsv-global` | RSV | Pathoplexus | Global | whole-genome | Global RSV (not Brazil-specific) |
| `orov-l-brazil` | Oropouche Virus | Pathoplexus | Brazil | whole-genome | Single-segment L template |
| `flu-h1n1-ha-brazil` | Influenza A H1N1 | NCBI | Brazil | whole-genome | Flu A H1N1 (HA only) |
| `flu-h3n2-ha-brazil` | Influenza A H3N2 | NCBI | Brazil | whole-genome | Flu A H3N2 (HA only) |
| `flu-b-ha-brazil` | Influenza B | NCBI | Brazil | whole-genome | Flu B (HA only) |
| `measles-b3-global` | Measles (MeV) | Pathoplexus | Global | whole-genome | Genotype B3 — `clade_filter` reference build |
| **`measles-b3-n450-global`** | **Measles (MeV)** | **Pathoplexus** | **Global** | **fragment** | **N450 gene — fragment-mode reference build** |
| `mayv-global` | Mayaro Virus | NCBI | Global | whole-genome | First no-dataset build (`viralqc.mode: skip`) |
| `local-example` | (User-defined) | Local | Brazil | whole-genome | Bring-your-own-data template |

## Template Selection Guide

### Choose Based on Data Source

- **Pathoplexus/LAPIS**: `denv3-brazil`, `rsv-a-brazil`, `chikv-brazil`
- **NCBI Entrez**: `zikv-brazil`, `flu-h1n1-ha-brazil`
- **Local files**: `local-example`

### Choose Based on Analysis Mode

- **Whole-genome** (standard): any build except `measles-b3-n450-global`
- **Fragment / gene window** (`mode: fragment`): `measles-b3-n450-global` — use this as the template for N450, flu HA, RSV F, etc.

### Choose Based on Virus Characteristics

- **Non-segmented** (e.g., DENV, ZIKV, CHIKV): `denv3-brazil`, `zikv-brazil`
- **Segmented** (single segment used, e.g., flu HA or RSV HA): `orov-l-brazil`, `flu-h1n1-ha-brazil`
- **Global scope**: `rsv-global` (no Brazil-specific filtering)

### Choose Based on Profile

- **Production-tuned**: `yfv-brazil` (UFBoot, confidence intervals, etc.)
- **First-pass/testing**: All others use simpler profiles; suitable for rapid exploration

## Data Source Details

### Pathoplexus Builds

These use [Pathoplexus/LAPIS](https://pathoplexus.globalhealthgenomics.org/) API:

- **Data**: Open-access surveillance sequences
- **Updates**: Real-time (new sequences appear immediately)
- **Coverage**: Brazil-focused (other regions available via query filters)
- **Template**: `denv3-brazil`, `rsv-a-brazil`

Example configuration:
```yaml
data_source: pathoplexus
pathoplexus:
  organism: "Dengue virus 3"
  query_params:
    dataUseTerms: OPEN
```

### NCBI Builds

These fetch from [NCBI Entrez](https://www.ncbi.nlm.nih.gov/nuccore/):

- **Data**: All public sequences by taxid
- **Updates**: Slower (weekly-ish refresh)
- **Coverage**: Global
- **Template**: `zikv-brazil`, `flu-h1n1-ha-brazil`

Example configuration:
```yaml
data_source: ncbi
ncbi:
  taxid: 11082
  email: ${NCBI_EMAIL}
  api_key: ${NCBI_API_KEY}
```

### Local Builds

Analyze sequences you provide:

- **Data**: Your metadata.tsv + sequences.fasta
- **Format**: Pathoplexus column conventions
- **Template**: `local-example`

Example configuration:
```yaml
data_source: local
local:
  metadata: /path/to/metadata.tsv
  sequences: /path/to/sequences.fasta
```

## Production Profiles

### YFV Brazil (Production-Tuned)

`builds/yfv-brazil/` is the reference for production-quality surveillance:

```yaml
parameters:
  ufboot: 1000
  model: "MFP"
  date_confidence: true
  traits_confidence: true
```

Use as a template for other pathogens where quality is paramount.

### All Others (First-Pass)

Default profile for rapid exploration:

```yaml
parameters:
  ufboot: 0
  model: "JC"
  date_confidence: false
  traits_confidence: false
```

Upgrade to production profile as needed for your surveillance program.

## Customization Examples

### Global vs Brazil-Specific

**Brazil (regional focus)**:
```yaml
region_source: division
colours: [continent, country, division]
subsample:
  group_by: [division, year]
```

**Global (country focus)**:
```yaml
region_source: country
colours: [continent, country, region]
subsample:
  group_by: [country, year]
```

### Including Reference Sequences

Ensure reference and known sentinel sequences are in `keep.txt`:

```bash
cat builds/denv3-brazil/keep.txt
NC_009996.1
known_denv3_reference
```

### Excluding Contaminants

Add problematic sequences to `ignore.txt`:

```bash
cat builds/denv3-brazil/ignore.txt
contaminated_seq_xyz
old_version_strain
```

## Quick Start by Pathogen

### DENV (Any Serotype)

Copy `builds/denv3-brazil/`, edit `config.yaml`:
- Change `organism` to your serotype (Dengue virus 1/2/4)
- Adjust `subsample.yaml` sequence counts if needed

### ZIKV

Copy `builds/zikv-brazil/` (NCBI data), or `builds/chikv-brazil/` (Pathoplexus) if available.

### RSV (Any Serotype)

Copy `builds/rsv-a-brazil/` or `rsv-b-brazil/`; change `organism` in config.

### Influenza (Specific Segment)

Copy relevant `builds/flu-*-brazil/` (HA only; other segments require separate builds).

### Your Pathogen

Copy and adapt `builds/local-example/` or a similar template. See [Adding a Pathogen](adding-a-pathogen.md).
