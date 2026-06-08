# Codex prompt: multi-build expansion & pipeline stress test

Use this document as the **full instruction set** for a Codex session whose goal is to scaffold, run, and learn from **13 new pathogen builds** in flexpipe. The session is as much about **discovering pipeline gaps** as about creating build directories.

---

## Mission

Expand flexpipe beyond the existing YFV Brazil and RSV Global scaffolds by implementing build configurations for the pathogens listed below. Treat each build as an **experiment**:

1. Scaffold the build under `builds/`.
2. Identify what is missing (reference, clades, Pathoplexus slug, taxid, ViralQC mapping, masking values, …).
3. **Ask the maintainer** for anything you cannot confidently resolve from public documentation.
4. Attempt dry-runs and (where feasible) partial or full pipeline runs.
5. Record failures, workarounds, and **pipeline inflexibilities** you hit.
6. Propose or implement **minimal pipeline improvements** where the same gap blocks multiple builds.

**Do not guess silently.** If a taxid, reference accession, Pathoplexus organism slug, or clade system is ambiguous, stop and ask. It is expected and encouraged to ask **many questions** — batch them per pathogen or per theme (e.g. “all Flu HA builds”) to keep review efficient.

---

## Context — read before coding

| Resource | Why |
|----------|-----|
| `CLAUDE.md` / `AGENTS.md` | Architecture, commands, config patterns |
| `README.md` § “Segmented viruses” | One build per segment; `expected_segment` for ViralQC |
| `docs/service_contract.md` | How `flexpipe-run`, workdirs, and resolved config work |
| `codex_review.md` | Known workflow risks and hardening history |
| `builds/yfv-brazil/` | **Template for Brazil-focused** Pathoplexus builds (`region_source: division`, Brazil subsample query) |
| `builds/rsv-global/` + `NOTES.md` | **Template for NCBI + scaffold gaps** documentation pattern |
| `viralQC/viralqc/config/datasets.yml` | Which viruses/segments ViralQC already knows |
| `tests/integration/test_ingest_wiring.py` | How ingest dry-run tests are structured |

**Existing builds (do not remove):**

- `builds/yfv-brazil/` — production-style YFV Brazil (Pathoplexus)
- `builds/rsv-global/` — RSV-A global NCBI scaffold (country-level subsampling)

---

## Build registry (13 targets)

All builds in this effort use **publicly available data only** (open Pathoplexus / NCBI). No restricted-access tokens unless the maintainer explicitly provides them.

| # | Source | Virus | Segment | Focus | Suggested directory |
|---|--------|-------|---------|-------|---------------------|
| 1 | Pathoplexus | Dengue virus 1 | (genome) | Brazil | `builds/denv1-brazil/` |
| 2 | Pathoplexus | Dengue virus 2 | (genome) | Brazil | `builds/denv2-brazil/` |
| 3 | Pathoplexus | Dengue virus 3 | (genome) | Brazil | `builds/denv3-brazil/` |
| 4 | Pathoplexus | Dengue virus 4 | (genome) | Brazil | `builds/denv4-brazil/` |
| 5 | NCBI | Zika virus | (genome) | Brazil | `builds/zikv-brazil/` |
| 6 | NCBI | Chikungunya virus | (genome) | Brazil | `builds/chikv-brazil/` |
| 7 | NCBI | Oropouche virus | **L** | Brazil | `builds/orov-l-brazil/` |
| 8 | Pathoplexus | Respiratory syncytial virus A | (genome) | Brazil | `builds/rsv-a-brazil/` |
| 9 | Pathoplexus | Respiratory syncytial virus B | (genome) | Brazil | `builds/rsv-b-brazil/` |
| 10 | NCBI | Influenza A H1N1 | **HA** | Brazil | `builds/flu-h1n1-ha-brazil/` |
| 11 | NCBI | Influenza A H3N2 | **HA** | Brazil | `builds/flu-h3n2-ha-brazil/` |
| 12 | NCBI | Influenza B | **HA** | Brazil | `builds/flu-b-ha-brazil/` |
| 13 | NCBI | SARS-CoV-2 | (genome) | Brazil | `builds/sarscov2-brazil/` |

**Column semantics:**

- **Source:** `data_source` in `config.yaml` — `pathoplexus` or `ncbi` (never both).
- **Segment:** Empty = whole genome / non-segmented workflow. `HA` or `L` = **single-segment build**; set `viralqc.expected_segment` and use a segment-appropriate reference and genome size. Full multi-segment fan-out is **out of scope** (see README).
- **Focus:**
  - **`Brazil`** — subsampling should **favor Brazilian sequences** while still allowing context sequences if the subsample schema supports it. Start from the YFV Brazil pattern: `region_source: division`, `coordinates.columns: "division location"`, subsample query `country == 'Brazil'`, `group_by: [division, year]`.
  - **`global`** (not in this table, but supported for future builds) — even geographic representation: `region_source: country`, `group_by: [country, year]` as in `builds/rsv-global/subsample.yaml`.

---

## Required layout per build

Each `builds/<name>/` directory should contain at minimum:

```
builds/<name>/
  config.yaml           # full flexpipe config
  subsample.yaml        # augur subsample schema (Brazil or global focus)
  auspice_config.json   # display settings (can start from yfv-brazil or rsv-global)
  clades.tsv            # mutation-based clade labels (placeholder + NOTES if unknown)
  reference.gb          # GenBank reference (placeholder + NOTES if not yet sourced)
  keep.txt              # strains to force-include (may be empty)
  ignore.txt            # reference accession(s) to exclude
  cache_coordinates.tsv # geocode seed (may be empty; runtime cache in workdir)
  NOTES.md              # **required** — gaps, questions, run log, blocker status
```

Optional as you learn:

- `STATUS.yaml` — machine-readable status enum: `scaffold | ingest_dry_run_ok | ingest_failed | phylo_dry_run_ok | blocked | runnable`
- Links to Nextstrain / WHO clade definitions used

---

## Scaffolding workflow (per build)

Execute in order. **Stop and ask** when a step lacks public, citable inputs.

### Phase A — Research & questions

For each build, determine and document:

| Field | Pathoplexus builds | NCBI builds |
|-------|-------------------|-------------|
| Organism / taxid | `pathoplexus.organism` (LAPIS slug — **verify on pathoplexus.org**) | `ncbi.taxid` |
| Genome size | From reference or literature | `ncbi.genome_size` (bp) |
| ViralQC virus | `viralqc.expected_virus` from `datasets.yml` | same |
| Segment | `viralqc.expected_segment` if segmented | same |
| Reference accession | Public GenBank record for align/tree | same |
| Terminal masking | `mask_5prime` / `mask_3prime` (reference-specific; 0 until calibrated) | same |
| Clade system | Nextclade clade column depth → `curation.clade_levels` | same |
| Subsample strategy | Brazil-focused `subsample.yaml` | same |

**Questions you should ask the maintainer** (examples — add your own):

- Preferred reference accession when several GenBank records exist?
- Brazil-only vs Brazil-focal-with-global-context subsampling policy?
- Minimum date window and `sequences_per_group` targets for surveillance use?
- For Flu HA builds: which reference strain (e.g. vaccine strain vs representative)?
- For Oropouche L: confirm segment-only scope and whether M/S segments are explicitly out of scope for this effort?
- Whether Pathoplexus organism names match LAPIS slugs for DENV1–4, RSV-A/B (verify URLs)?
- `NCBI_EMAIL` / API key for automated fetch tests?
- Acceptable workdir root for test runs (e.g. `/tmp/flexpipe-builds/<name>`)?

### Phase B — Scaffold files

1. Copy the closest template (`yfv-brazil` for Pathoplexus+Brazil, `rsv-global` for NCBI).
2. Adjust `config.yaml`: data source, region, coordinates, traits, QC columns, ViralQC keys, masking, `files.*` paths.
3. Write `subsample.yaml` matching **Focus** column.
4. Write `NOTES.md` listing every placeholder and open question.

### Phase C — Validate wiring (no network)

```bash
# From repo root — adjust paths per build
flexpipe-run --config builds/<name>/config.yaml \
  --workdir /tmp/flexpipe-runs/<name> \
  --stage ingest --cores 2
# Stop after dry-run inspection OR use snakemake --dry-run via integration test pattern
```

Add or extend `tests/integration/` dry-run coverage for **each new build directory** (mirror `test_ingest_wiring.py`). Phylo dry-run tests should be added where `reference.gb` is still a placeholder — expect documented failure modes.

### Phase D — Run and learn

When maintainer approves references and credentials:

```bash
conda activate nextstrain
# ViralQC env must exist: bash scripts/install_viralqc.sh

flexpipe-run \
  --config builds/<name>/config.yaml \
  --workdir /tmp/flexpipe-runs/<name> \
  --run-date YYYY-MM-DD \
  --stage ingest   # then phylo when ingest succeeds
```

For each failure, record in `NOTES.md`:

- **Stage** (fetch, viralqc, curate, subsample, align, …)
- **Error excerpt**
- **Root cause** (missing file, wrong slug, pipeline limitation, …)
- **Fix applied** (config change) vs **pipeline change needed** (issue for codebase)

### Phase E — Improve the pipeline (when justified)

If the **same limitation** blocks ≥2 builds, implement a **minimal** fix with tests. Examples from prior reviews:

- Path resolution / cwd independence
- Optional Snakemake flags when config values empty
- Clearer error when Pathoplexus organism 404s
- Segmented-virus validation messaging
- Subsample path resolution in resolved config
- Integration test template parameterized by build name

Avoid large refactors. Prefer one PR theme per pipeline fix.

---

## Deliverables

### 1. `builds/` tree

All 13 directories scaffolded with consistent naming and complete `NOTES.md`.

### 2. `builds/BUILD_ROSTER.md` (create this)

Summary table:

| Build | Source | Focus | Ingest dry-run | Ingest live | Phylo dry-run | Blockers | Open questions |
|-------|--------|-------|----------------|-------------|---------------|----------|----------------|

Update as you progress.

### 3. `builds/GAPS_LOG.md` (create this)

Cumulative list of **pipeline inflexibilities** discovered, e.g.:

- Config keys that exist but are ignored
- Pathogens missing from ViralQC bundled datasets
- Pathoplexus organisms with no public LAPIS endpoint
- Segmented-virus footguns
- Subsample patterns that cannot express “Brazil-heavy but not Brazil-only”
- Missing integration test coverage

Each entry: **symptom → evidence → suggested fix → priority**.

### 4. Tests

- Extend `tests/integration/` so every scaffold build has at least an **ingest Snakemake dry-run** test.
- Add phylo dry-runs where reference is valid; document skips in test docstring where placeholder reference is intentional.

### 5. Optional code changes

Only where gaps are real and fixes are small. Document in `HARDENING_CHANGELOG.md` or a short `builds/PIPELINE_FIXES.md` section.

---

## Constraints

- **Public data only** for this effort.
- **No secrets in git** — use env vars (`NCBI_EMAIL`, `NCBI_API_KEY`, `PPX_AUTH_TOKEN`) documented in NOTES, not committed.
- **Do not** run destructive git operations or push without explicit approval.
- **Segmented viruses:** one build per segment; document limitations honestly in NOTES (see README).
- **Do not** duplicate `yfv-brazil` or remove `rsv-global`; new RSV builds are Brazil-focused Pathoplexus variants alongside the global NCBI scaffold.
- Prefer **asking questions** over inventing biological parameters (taxids, references, masking numbers).

---

## Verification baseline

After scaffold + any pipeline changes:

```bash
conda run -n nextstrain pytest
conda run -n nextstrain pytest -m integration
conda run -n nextstrain ruff check .
conda run -n nextstrain black --check .
conda run -n nextstrain mypy flexpipe/ --ignore-missing-imports
```

---

## Suggested execution order

Work in batches to maximize learning transfer:

1. **DENV1–4 (Pathoplexus, Brazil)** — shared dengue patterns; verify four LAPIS organisms.
2. **ZIKV + CHIKV (NCBI, Brazil)** — arbovirus NCBI fetch + ViralQC (`zikav`, `chikv` in datasets.yml).
3. **RSV-A + RSV-B (Pathoplexus, Brazil)** — compare with existing `rsv-global` NCBI scaffold.
4. **SARS-CoV-2 (NCBI, Brazil)** — high volume; stress fetch and subsampling.
5. **Oropouche L (NCBI, Brazil)** — segmented; validates `expected_segment` path.
6. **Flu H1N1 / H3N2 / B HA (NCBI, Brazil)** — three segment builds; shared HA reference questions.

Within each batch: scaffold all → dry-run all → collect questions → **pause for maintainer answers** → run live → update GAPS_LOG.

---

## Question policy (critical)

> **Ask as many questions as necessary.** A long, well-organized question list is a successful intermediate deliverable.

Format questions as:

```markdown
## Questions for maintainer — batch <N> (<theme>)

### <build-name>
1. ...
2. ...

### Pipeline / cross-cutting
1. ...
```

Mark each question **blocking** (cannot proceed) vs **non-blocking** (scaffold with placeholder). Do not fabricate GenBank accessions, taxids, or Pathoplexus slugs to unblock yourself.

---

## Success criteria

- [ ] 13 build directories exist with standard file layout and `NOTES.md`
- [ ] `BUILD_ROSTER.md` and `GAPS_LOG.md` maintained throughout the session
- [ ] Every build has ingest dry-run test coverage or a documented skip reason
- [ ] All blocking biological/config questions collected and presented before guessing
- [ ] At least one end-to-end ingest success (maintainer-provided credentials permitting) OR clear documented blockers per build
- [ ] Pipeline gaps catalogued with actionable follow-ups
- [ ] Unit + integration tests pass; no unrelated refactors

---

## Start here

1. Read the context files listed above.
2. Create `builds/BUILD_ROSTER.md` and `builds/GAPS_LOG.md`.
3. Begin **batch 1 (DENV1–4)**: research Pathoplexus organisms, scaffold four directories, run dry-runs, write questions.
4. Present findings and questions before moving to live runs or batch 2.
