# plan_builds_continuation.md

Repeatable loop for the remaining pathogen builds in `plan_builds.md`.

```
scaffold minimalist build
  → dry-run (pytest -m integration)
  → live ingest (if credentials + ViralQC available)
  → record failures in GAPS_LOG.md
  → minimal pipeline fix + unit/integration test
  → update BUILD_ROSTER.md + PIPELINE_FIXES.md
  → commit, repeat
```

---

## 1. Minimal Build Template

The smallest file set to exercise a new pathogen:

```
builds/<name>/
  config.yaml           # full flexpipe config (see template below)
  subsample.yaml        # augur subsample schema
  auspice_config.json   # copy from yfv-brazil and update title/colorings
  clades.tsv            # header-only placeholder is OK for first pass
  reference.gb          # REAL GenBank record required (placeholder → phylo tests skip)
  keep.txt              # empty
  ignore.txt            # reference accession only
  cache_coordinates.tsv # empty first line (header required by cache merge)
```

**config.yaml first-pass profile** (copy/adapt from `builds/denv3-brazil/config.yaml`):

```yaml
# Annotate each field; copy ALL sections from denv3-brazil and change:
#   pathoplexus.organism / ncbi.taxid + ncbi.genome_size
#   viralqc.expected_virus (+  viralqc.expected_segment for segmented builds)
#   files.* paths pointing into this build directory
#   parameters.mask_5prime / mask_3prime (set 0 until calibrated)
#   curation.clade_levels, curation.lineage_parser

parameters:
  mask_5prime:    0      # set to 0 until reference-specific values are known
  mask_3prime:    0
  mask_sites:     ""
  mask_sites_file: ""
  ufboot:         0      # first-pass: no UFBoot support (fast)
  model:          "JC"   # first-pass: fast fixed model
  root:           "least-squares"
  coalescent:     "skyline"
  date_inference: "marginal"
  divergence_units: "mutations"
  date_confidence:    false   # first-pass: skip date confidence (speed)
  traits_confidence:  false   # first-pass: skip trait confidence (speed)
  ancestral_inference: "joint"
```

**Definition of "minimalist build":**
- Real `reference.gb` required (placeholder → phylo integration test is auto-skipped).
- Header-only `clades.tsv` is intentional; `augur clades` produces empty branch labels, but
  metadata `clade` from ViralQC drives colouring and filtering.
- Lightweight phylo (`JC`, `ufboot: 0`, confidence disabled) for first-pass analyses.
- No `keep.txt` entries, no `mask_sites`, no BED file.

---

## 2. Priority Queue

DENV1–4 are complete (dry-run + live + phylo). Remaining builds from `plan_builds.md`:

| Priority | Build | Source | Segment | Notes |
|----------|-------|--------|---------|-------|
| **1** | `zikv-brazil` | NCBI | genome | Small dataset; fast. taxid 64320, NC_035889.1 |
| **1** | `chikv-brazil` | NCBI | genome | taxid 37124; ViralQC `chikv` dataset present |
| **2** | `rsv-a-brazil` | Pathoplexus | genome | Brazil-focal variant of existing `rsv-global` |
| **2** | `rsv-b-brazil` | Pathoplexus | genome | Pair with rsv-a-brazil |
| **3** | `sarscov2-brazil` | NCBI | genome | High-volume; stress fetch + subsampling |
| **4** | `orov-l-brazil` | NCBI | **L** | Segmented; validates `expected_segment` path |
| **5** | `flu-h1n1-ha-brazil` | NCBI | **HA** | Three Flu builds; batch questions on reference strain |
| **5** | `flu-h3n2-ha-brazil` | NCBI | **HA** | |
| **5** | `flu-b-ha-brazil` | NCBI | **HA** | |

**Rationale:** ZIKV + CHIKV are smaller NCBI datasets and provide good pipeline stress-testing
before the high-volume SARS-CoV-2 run. RSV-A/B add the Pathoplexus→Brazil pattern alongside
the existing NCBI global RSV scaffold. Flu HA and Oropouche introduce per-segment builds; batch
the Flu questions together for efficiency.

---

## 3. Standard Commands (parameterized by `BUILD`)

```bash
# Set once per session
BUILD=zikv-brazil
WORKDIR=/tmp/flexpipe-runs/$BUILD
RUN_DATE=$(date +%Y-%m-%d)

# Ingest dry-run (no network, no ViralQC)
snakemake --snakefile ingest/Snakefile \
  --configfile builds/$BUILD/config.yaml \
  --config workdir=$WORKDIR \
  --dry-run --printshellcmds --cores 4

# Or via integration test (preferred — runs from outside repo):
conda run -n nextstrain pytest -m integration \
  -k "test_all_scaffold_builds_dry_run[$BUILD]" -v

# Live ingest (needs network + ViralQC env)
conda activate nextstrain
flexpipe-run \
  --config builds/$BUILD/config.yaml \
  --workdir $WORKDIR \
  --run-date $RUN_DATE \
  --stage ingest \
  --cores 4

# Live phylo (after ingest)
flexpipe-run \
  --config builds/$BUILD/config.yaml \
  --workdir $WORKDIR \
  --run-date $RUN_DATE \
  --stage phylo \
  --cores 4

# Full run
flexpipe-run \
  --config builds/$BUILD/config.yaml \
  --workdir $WORKDIR \
  --run-date $RUN_DATE \
  --cores 4

# Visualize
auspice view --datasetDir $WORKDIR/auspice/
# → http://localhost:4000
```

---

## 4. Gap Taxonomy

When a build fails, classify the root cause:

| Class | Description | Resolution |
|-------|-------------|------------|
| `config-only` | Wrong taxid, organism slug, genome_size, mask values, column name | Edit `config.yaml`; no code change |
| `pipeline bug` | Code path missing, broken, or crashing for this pathogen | Fix in `flexpipe/` or Snakefile + test + PIPELINE_FIXES.md |
| `missing biological input` | Reference, clade TSV, ViralQC dataset not yet available | Placeholder + NOTES.md; ask maintainer |
| `out-of-scope` | Multi-segment fan-out, closed-access data, external service limit | Document in GAPS_LOG.md; no action |

**Worked examples from Batch 1 (DENV):**

| Symptom | Class | Resolution |
|---------|-------|------------|
| Pathoplexus returns all dengue serotypes mixed | `config-only` | Added `pathoplexus.query_params.serotype` |
| FASTA headers `PP_XXX|DENV-1` don't match metadata | `pipeline bug` | Added `pathoplexus.strip_fasta_id_suffix` + tests |
| `augur mask --mask-from-beginning 0` exits with error | `pipeline bug` | Copy branch in Snakefile + tests |
| `augur clades` exits on header-only TSV | `pipeline bug` | Fallback to empty clade node data |
| Clade TSV mutation definitions unknown | `missing biological input` | Placeholder + maintainer question |

---

## 5. CI Strategy

| Scenario | Coverage |
|----------|----------|
| Every scaffold build | **Ingest dry-run test** (`test_all_scaffold_builds_dry_run[<name>]`) auto-parametrized via `BUILD_CONFIGS` list in `test_ingest_wiring.py` |
| Real reference (non-PLACEHOLDER) | **Phylo dry-run test** (`test_denv_phylo_dry_run_when_reference_is_real`) — auto-skips when `reference.gb` contains `PLACEHOLDER` |
| Live ingest | **Manual only** — requires network, credentials, ViralQC env |
| Live end-to-end | **Manual only** |

**Adding a new build to CI:**

1. Add the build config path to `BUILD_CONFIGS` in `tests/integration/test_ingest_wiring.py`.
2. Add to `DENV_BUILD_CONFIGS` (or a new pathogen-family list) if there are family-specific assertions.
3. Add to `DENV_BUILD_CONFIGS` in `tests/integration/test_phylo_wiring.py` for phylo dry-run.
4. The `test_all_scaffold_builds_dry_run` and `test_denv_phylo_dry_run_when_reference_is_real`
   tests will pick up the new build automatically via parametrize.

---

## 6. Questions to Ask Before Each Batch

Before live runs or committing build files, collect and batch these per pathogen:

- [ ] Preferred reference accession (when multiple GenBank records exist)?
- [ ] Brazil-only vs Brazil-focal-with-global-context subsampling?
- [ ] `sequences_per_group` target for surveillance use?
- [ ] For segmented builds: confirm scope (L only for Oropouche? HA only for Flu?)?
- [ ] For Flu: which reference strain (current WHO vaccine strain vs representative clade)?
- [ ] ViralQC dataset present? (`viralQC/viralqc/config/datasets.yml`)
- [ ] `NCBI_EMAIL` + optional `NCBI_API_KEY` set for NCBI builds?
- [ ] Terminal mask values (`mask_5prime`, `mask_3prime`) for the chosen reference?

---

## 7. Session Handoff Checklist

After each build batch:

- [ ] `builds/BUILD_ROSTER.md` updated (ingest dry-run, live status, blockers)
- [ ] `builds/GAPS_LOG.md` updated with any new pipeline limitations
- [ ] `builds/PIPELINE_FIXES.md` updated for any code changes
- [ ] Unit + integration tests pass (`pytest -q && pytest -m integration -q`)
- [ ] `ruff check . && black --check . && mypy flexpipe/ --ignore-missing-imports` clean
- [ ] Commit staged (code + docs); planning markdown left untracked unless asked
