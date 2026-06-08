# Claude prompt: remaining pathogen builds (continuation)

Implement the plan in `plan_builds_continuation.md`. Continue the multi-build expansion started in `plan_builds.md`. DENV1–4 are **done** — do not redo them. Your job is to scaffold, run, and learn from the **remaining** builds below.

**Do not include SARS-CoV-2** (`sarscov2-brazil`) in this session — the dataset is too large; the maintainer will handle it separately.

---

## Mission

For each remaining pathogen build, treat the work as an **experiment**:

1. Scaffold a minimalist build under `builds/`.
2. Run ingest dry-run → live ingest → live phylo → full end-to-end where possible.
3. Record failures, workarounds, and pipeline inflexibilities.
4. Implement **minimal pipeline fixes** when the same gap blocks multiple builds (with unit/integration tests).
5. Update tracking docs after each build or batch.

**Ask as many questions as you need.** Batch them by pathogen or theme (e.g. all Flu HA builds). Do not guess silently on taxids, reference accessions, Pathoplexus slugs, masking values, or subsampling policy.

---

## Read first

| Resource | Why |
|----------|-----|
| `CLAUDE.md` | Architecture, commands, config patterns |
| `plan_builds_continuation.md` | **Primary workflow** — template, commands, gap taxonomy, CI strategy |
| `plan_builds.md` | Full context, deliverables, question policy |
| `builds/BUILD_ROSTER.md` | Current status (DENV1–4 complete) |
| `builds/GAPS_LOG.md` | Known pipeline limitations |
| `builds/PIPELINE_FIXES.md` | Prior code fixes from Batch 1 |
| `builds/denv3-brazil/` | **First-pass config template** (Pathoplexus + Brazil) |
| `builds/rsv-global/` + `NOTES.md` | NCBI scaffold pattern |
| `viralQC/viralqc/config/datasets.yml` | ViralQC dataset availability |
| `tests/integration/test_ingest_wiring.py` | How to register builds in CI |

---

## Remaining builds (8 targets — no SARS-CoV-2)

Work in priority order from `plan_builds_continuation.md` §2:

| Priority | Build | Source | Segment | Notes |
|----------|-------|--------|---------|-------|
| **1** | `zikv-brazil` | NCBI | genome | taxid 64320, NC_035889.1 |
| **1** | `chikv-brazil` | NCBI | genome | taxid 37124; ViralQC `chikv` dataset |
| **2** | `rsv-a-brazil` | Pathoplexus | genome | Brazil-focal variant of `rsv-global` |
| **2** | `rsv-b-brazil` | Pathoplexus | genome | Pair with rsv-a-brazil |
| **4** | `orov-l-brazil` | NCBI | **L** | Segmented; set `viralqc.expected_segment` |
| **5** | `flu-h1n1-ha-brazil` | NCBI | **HA** | Batch Flu questions together |
| **5** | `flu-h3n2-ha-brazil` | NCBI | **HA** | |
| **5** | `flu-b-ha-brazil` | NCBI | **HA** | |

**Excluded:** `sarscov2-brazil` — out of scope for this session.

---

## Per-build loop

Follow `plan_builds_continuation.md` §1–3 exactly:

```
scaffold minimalist build
  → dry-run (pytest -m integration)
  → live ingest (if credentials + ViralQC available)
  → live phylo + full end-to-end run
  → record failures in GAPS_LOG.md
  → minimal pipeline fix + unit/integration test (if needed)
  → update BUILD_ROSTER.md + PIPELINE_FIXES.md
  → commit, repeat
```

### Minimal build template

```
builds/<name>/
  config.yaml           # adapt from builds/denv3-brazil/config.yaml
  subsample.yaml
  auspice_config.json   # copy from yfv-brazil, update title/colorings
  clades.tsv            # header-only placeholder OK for first pass
  reference.gb          # REAL GenBank record required
  keep.txt              # empty
  ignore.txt            # reference accession only
  cache_coordinates.tsv # header row only
  NOTES.md              # gaps, questions, run log
```

**First-pass phylo profile** (speed over accuracy):

- `mask_5prime: 0`, `mask_3prime: 0` until calibrated
- `model: "JC"`, `ufboot: 0`
- `date_confidence: false`, `traits_confidence: false`

### Standard commands

```bash
BUILD=zikv-brazil   # change per build
WORKDIR=/tmp/flexpipe-runs/$BUILD
RUN_DATE=$(date +%Y-%m-%d)

# Dry-run (preferred)
conda run -n nextstrain pytest -m integration \
  -k "test_all_scaffold_builds_dry_run[$BUILD]" -v

# Live ingest
flexpipe-run --config builds/$BUILD/config.yaml \
  --workdir $WORKDIR --run-date $RUN_DATE --stage ingest --cores 4

# Live phylo
flexpipe-run --config builds/$BUILD/config.yaml \
  --workdir $WORKDIR --run-date $RUN_DATE --stage phylo --cores 4

# Full end-to-end (required for each build)
flexpipe-run --config builds/$BUILD/config.yaml \
  --workdir $WORKDIR --run-date $RUN_DATE --cores 4
```

Always pass `--run-date` explicitly for reproducible subsampling.

---

## Questions to ask (batch before live runs)

Per `plan_builds_continuation.md` §6 — ask the maintainer when ambiguous:

- Preferred reference accession?
- Brazil-only vs Brazil-focal-with-global-context subsampling?
- `sequences_per_group` target?
- Segmented builds: confirm scope (L only for Oropouche? HA only for Flu?)
- Flu: which reference strain (vaccine vs representative clade)?
- ViralQC dataset present in `datasets.yml`?
- `NCBI_EMAIL` / `NCBI_API_KEY` available?
- Terminal mask values for the chosen reference?

Format as:

```markdown
## Questions for maintainer — batch N (<theme>)

### <build-name>
1. [blocking/non-blocking] ...

### Pipeline / cross-cutting
1. ...
```

Proceed with placeholders for **non-blocking** items; stop and ask for **blocking** ones.

---

## Gap taxonomy

When a build fails, classify per `plan_builds_continuation.md` §4:

| Class | Action |
|-------|--------|
| `config-only` | Edit `config.yaml` |
| `pipeline bug` | Fix in `flexpipe/` or Snakefile + test + `PIPELINE_FIXES.md` |
| `missing biological input` | Placeholder + `NOTES.md`; ask maintainer |
| `out-of-scope` | Document in `GAPS_LOG.md` only |

---

## CI registration

After scaffolding each build:

1. Add config path to `BUILD_CONFIGS` in `tests/integration/test_ingest_wiring.py`.
2. Add to phylo dry-run list in `tests/integration/test_phylo_wiring.py` when `reference.gb` is real (non-PLACEHOLDER).

---

## Deliverables

- [ ] 8 build directories with standard layout + `NOTES.md`
- [ ] `builds/BUILD_ROSTER.md` updated after each build (ingest dry-run, live, phylo, blockers)
- [ ] `builds/GAPS_LOG.md` updated with new pipeline limitations
- [ ] `builds/PIPELINE_FIXES.md` updated for any code changes
- [ ] Integration tests pass for all new builds
- [ ] **End-to-end run** (`flexpipe-run` ingest + phylo) for each build, or a documented blocker in BUILD_ROSTER
- [ ] Commits for code + build files (planning markdown can stay untracked unless asked)

---

## Verification before each commit

```bash
conda run -n nextstrain pytest -q
conda run -n nextstrain pytest -m integration -q
conda run -n nextstrain ruff check .
conda run -n nextstrain black --check .
conda run -n nextstrain mypy flexpipe/ --ignore-missing-imports
```

---

## Constraints

- **Public data only** — no secrets in git (`NCBI_EMAIL`, `NCBI_API_KEY`, `PPX_AUTH_TOKEN` via env).
- **Do not** remove or modify `yfv-brazil`, `rsv-global`, or the completed DENV builds.
- **Segmented viruses:** one build per segment; no multi-segment fan-out (see `CLAUDE.md`).
- **Do not** run destructive git operations or push without explicit approval.
- Prefer minimal, focused diffs over refactors.

---

## Start here

1. Read `CLAUDE.md`, `plan_builds_continuation.md`, and `builds/BUILD_ROSTER.md`.
2. Confirm environment: `conda activate nextstrain`, ViralQC installed (`bash scripts/install_viralqc.sh`).
3. Begin **Priority 1**: scaffold `zikv-brazil` and `chikv-brazil`, dry-run, then ask any blocking questions before live runs.
4. Run each build **end-to-end** before moving to the next priority batch.
5. Present findings and open questions after Priority 1 before starting Priority 2 (RSV), unless all blocking questions are already resolved.
