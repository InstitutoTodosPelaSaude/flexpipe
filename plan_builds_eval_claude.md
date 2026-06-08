# Claude prompt: evaluate multi-build expansion work

You previously implemented pathogen builds following `plan_builds_continuation.md` (and `plan_builds_claude.md` if used). **Your task now is twofold:**

1. **Operational review** — critically audit deliverables, code quality, tests, and documentation.
2. **Empirical synthesis** — distill what running the workflow across many pathogens taught us about flexpipe's strengths, gaps, and recurring patterns — and write that up as a durable markdown artifact.

Be honest, evidence-based, and specific. Cite file paths, commit hashes, test names, and config keys when making claims.

**Do not re-run live pipeline jobs unless needed to verify a specific claim.** Prefer inspecting the repo, git history, tests, and tracking docs. Re-run tests and linters yourself.

**Do not continue building new pathogen configs** unless the user explicitly asks afterward.

---

## Evaluation scope

### In scope

All work attributable to the continuation plan:

| Priority | Build | Expected minimum |
|----------|-------|------------------|
| 1 | `zikv-brazil`, `chikv-brazil` | Scaffold + ingest dry-run + **live end-to-end** |
| 2 | `rsv-a-brazil`, `rsv-b-brazil` | Scaffold + ingest dry-run + **live end-to-end** |
| 4 | `orov-l-brazil` | Scaffold + segmented config + **live end-to-end** |
| 5 | `flu-h1n1-ha-brazil`, `flu-h3n2-ha-brazil`, `flu-b-ha-brazil` | Scaffold + ingest dry-run + phylo dry-run (live ingest optional if blocked) |

Also review **pipeline fixes** and **Batch 1 carryover** (DENV1–4) only where they intersect with continuation work (shared code paths, regressions, doc drift).

### Out of scope

- `sarscov2-brazil` — intentionally excluded from this effort
- Unrelated refactors outside the build-expansion work
- Production-grade phylogenetics tuning (UFBoot, MFP, calibrated masks) — note as follow-ups, do not penalize first-pass profile

---

## Read first

| Resource | Why |
|----------|-----|
| `plan_builds_continuation.md` | Original requirements and handoff checklist |
| `plan_builds_claude.md` | Session instructions (if present) |
| `builds/BUILD_ROSTER.md` | Claimed status per build |
| `builds/GAPS_LOG.md` | Documented pipeline limitations |
| `builds/PIPELINE_FIXES.md` | Code changes and rationale |
| `builds/*/NOTES.md` | Per-build run logs and open questions |
| `CLAUDE.md` | Project conventions and architecture |
| `git log --oneline` (recent) | What was actually committed |

Inspect each new `builds/<name>/` directory and any changed files under `flexpipe/`, `ingest/`, `phylogenetic/`, and `tests/`.

Cross-reference all four tracking layers — they should tell a coherent story:

- `BUILD_ROSTER.md` — *what ran*
- `GAPS_LOG.md` — *what broke and why*
- `PIPELINE_FIXES.md` — *what we changed in code*
- **`builds/MULTI_BUILD_LEARNINGS.md`** — *what we learned globally* (you will create or refresh this; see below)

---

## Verification commands (run these)

```bash
# Unit + integration
conda run -n nextstrain pytest -q
conda run -n nextstrain pytest -m integration -q

# Lint / types
conda run -n nextstrain ruff check .
conda run -n nextstrain black --check .
conda run -n nextstrain mypy flexpipe/ --ignore-missing-imports

# Per-build dry-run spot checks (adjust BUILD)
BUILD=zikv-brazil
conda run -n nextstrain pytest -m integration \
  -k "test_all_scaffold_builds_dry_run[$BUILD]" -v
```

Cross-check BUILD_ROSTER claims against git diffs and test parametrization lists in:
- `tests/integration/test_ingest_wiring.py`
- `tests/integration/test_phylo_wiring.py`

---

## Evaluation rubric

Score each dimension **1–5** (1 = poor/missing, 3 = acceptable, 5 = excellent). Provide a one-line justification and concrete evidence for every score.

| Dimension | What to assess |
|-----------|----------------|
| **Plan completeness** | All in-scope builds scaffolded; per-build loop followed (scaffold → dry-run → live → docs → commit); handoff checklist in `plan_builds_continuation.md` §7 |
| **Biological / config accuracy** | Correct taxids, references, genome sizes, Pathoplexus slugs, `viralqc.expected_virus` / `expected_segment`, subsample queries, Brazil-focal strategy; no silent guessing on ambiguous inputs |
| **Build file quality** | Minimal template compliance (§1); first-pass phylo profile; real `reference.gb`; consistent `files.*` paths; valid `subsample.yaml` schema (`samples:` not `subsamples:`) |
| **Pipeline fix quality** | Fixes minimal and targeted; root cause documented in GAPS_LOG; no over-engineering; regressions unlikely |
| **Code standards** | Matches repo style; ruff/black/mypy clean; sensible naming; no dead code; no secrets committed |
| **Test coverage** | Every new build in `BUILD_CONFIGS`; phylo dry-run where reference is real; unit tests for each pipeline fix; tests assert behavior not implementation trivia |
| **Documentation** | BUILD_ROSTER accurate and current; GAPS_LOG entries have symptom/evidence/fix/priority; PIPELINE_FIXES matches code; per-build `NOTES.md` where gaps exist; open questions captured |
| **Operational evidence** | Live run counts, workdirs, dates in BUILD_ROSTER are plausible; failures classified with gap taxonomy (§4); blockers honestly stated |
| **Maintainability** | Future builds can copy patterns; config comments helpful; no one-off hacks without explanation |
| **Empirical synthesis** | Cross-pathogen patterns identified; config-vs-code fix ratio understood; recurring footguns documented; learnings actionable for the next batch (SARS-CoV-2, production profiles) |

---

## Deep-dive checklist

Work through each section and record **pass / partial / fail** with evidence.

### 1. Build inventory

For each in-scope build directory, confirm presence and quality of:

- `config.yaml`, `subsample.yaml`, `auspice_config.json`, `clades.tsv`, `reference.gb`, `keep.txt`, `ignore.txt`, `cache_coordinates.tsv`
- Optional but expected: `NOTES.md` when placeholders or open questions exist

Flag:
- Placeholder references where real GenBank was required
- Wrong data source (NCBI vs Pathoplexus)
- Deviations from first-pass phylo profile without documentation
- Copy-paste errors between similar builds (e.g. wrong taxid, wrong ignore.txt accession)

### 2. Config correctness

Spot-check against public sources and `viralQC/viralqc/config/datasets.yml`:

- NCBI: `ncbi.taxid`, `ncbi.genome_size`, fetch email handling
- Pathoplexus: organism slug verifiable on LAPIS
- Segmented builds: `expected_segment` matches reference segment; scope is single-segment only
- Flu builds: rationale for empty `expected_virus` and segment `"4"`
- RSV builds: rationale for empty `expected_virus` vs blast.tsv naming mismatch
- Subsample: Brazil focal + context pattern consistent with DENV/YFV template
- `region_source`, `coordinates.columns`, `traits.columns` coherent for Brazil builds

### 3. Pipeline changes

Review every code change introduced during the expansion:

- Is the fix the **smallest** change that solves the problem?
- Is it covered by unit and/or integration tests?
- Does GAPS_LOG classify it correctly (`config-only` vs `pipeline bug`)?
- Could it break existing builds (`yfv-brazil`, `denv1-4`, `rsv-global`)?

Known areas to verify (from GAPS_LOG — confirm implementation quality, not just existence):

- NCBI INSDC sentinel normalization (`flexpipe/ingest/ncbi.py`)
- Pathoplexus query params / FASTA ID suffix stripping
- ViralQC join hardening (`flexpipe/curate/viralqc_join.py`)
- Phylo optional steps: empty clades, zero masks, `ufboot: 0`, confidence flags
- Hybrid geography / continent column (if implemented)
- Trait state capping / lineage parsers (if implemented)

### 4. Test coverage

- All new builds listed in `BUILD_CONFIGS`?
- Phylo dry-run parametrization covers NCBI, Pathoplexus, and segmented families separately?
- Unit tests exist for each non-trivial Python fix?
- Any `@pytest.mark.skip` or overly broad mocks hiding real failures?
- Integration tests runnable from outside repo root (cwd independence)?

Report **gaps**: builds or code paths without dry-run coverage.

### 5. Documentation accuracy

Compare **claims vs reality**:

- Does BUILD_ROSTER overstate success (e.g. "OK live" without evidence)?
- Are flu builds correctly marked if only phylo dry-run completed?
- Does GAPS_LOG duplicate or contradict PIPELINE_FIXES?
- Are open questions from §6 still unanswered but blocking production use?
- Any planning markdown committed that should stay untracked?

### 6. Code standards & hygiene

- `ruff`, `black`, `mypy` results
- Commit message quality and logical grouping (builds vs pipeline fixes)
- No credentials, tokens, or large binary artifacts in git
- No unrelated drive-by changes

### 7. Regressions & risk

- Would changes to shared Snakefile rules affect production YFV build?
- Any TODO/FIXME left in committed code without GAPS_LOG entry?
- Technical debt introduced that blocks the next batch (SARS-CoV-2, production phylo profiles)?

### 8. Cross-pathogen empirical synthesis

Go beyond per-build pass/fail. The multi-build effort was an **experiment on flexpipe itself**. Answer:

**Workflow learnings**

- Which stages failed most often across pathogens (fetch, viralqc, curate, subsample, align, tree, export)?
- Did failures cluster by data source (NCBI vs Pathoplexus), segment type (genome vs L/HA), or build batch?
- How often was the fix `config-only` vs `pipeline bug` vs `missing biological input`? (Use gap taxonomy §4.)
- What surprised you only after live runs (not visible in dry-runs)?

**Recurring patterns**

- Config fields that look generic but are pathogen-specific (`expected_virus`, subsample schema, query params).
- Template drift: where did scaffolds copy the wrong pattern (e.g. `subsamples:` vs `samples:`)?
- ViralQC naming mismatches (blast.tsv vs results.tsv vs Nextclade dataset names).
- Geography / subsampling tradeoffs for Brazil-focal + global context builds.
- Runtime bottlenecks (IQ-TREE, geocoding, fetch volume) and how first-pass phylo profile mitigated them.

**What flexpipe handles well today**

- Capabilities validated across ≥3 pathogen families without code changes.
- Config knobs that scaled cleanly (document with examples).

**What flexpipe still cannot express**

- Gaps that blocked or degraded multiple builds; items still in GAPS_LOG with `Status: Documented; no code change yet`.
- Features that would unlock the next wave (SARS-CoV-2 volume, production phylo, segmented fan-out).

**Adjustments map**

Produce a consolidated view of every code adjustment, not just a fix audit:

| Adjustment | Triggered by (builds) | Files changed | Tests added | Still needed? |
|------------|----------------------|---------------|-------------|---------------|

Include config-only adjustments that became **de facto conventions** (empty `expected_virus` for flu/RSV, first-pass phylo profile, etc.).

**Recommendations for future scaffolds**

- Updated checklist or template deltas for `plan_builds_continuation.md` §1.
- Which build is the best template per archetype: NCBI genome, Pathoplexus Brazil, segmented NCBI.

---

## Primary deliverable: `builds/MULTI_BUILD_LEARNINGS.md`

**Write or refresh this file** as part of the evaluation. It is the durable synthesis artifact — not a session transcript. Merge and deduplicate content from `GAPS_LOG.md`, `PIPELINE_FIXES.md`, and per-build `NOTES.md`; do not merely copy them.

Use this structure:

```markdown
# Multi-Build Learnings

> Synthesis from empirical flexpipe runs across DENV1–4 and continuation builds
> (ZIKV, CHIKV, RSV-A/B, OROV-L, Flu HA). Last updated: YYYY-MM-DD.

## Executive synthesis

3–5 paragraphs: what running many pathogens taught us about flexpipe as a
generalizable pipeline vs a YFV/DENV-specialized one.

## Pathogen coverage matrix

| Build | Source | Segment | Live E2E | Key friction | Fix class |
|-------|--------|---------|----------|--------------|-----------|

## Learnings by pipeline stage

### Ingest (fetch, merge, ViralQC)
- …

### Curation & QC
- …

### Subsampling & geography
- …

### Phylogenetics & export
- …

### Visualization (colors, coordinates, Auspice)
- …

## Code adjustments compendium

All pipeline code changes from this effort, chronologically or by theme.
For each entry:
- **Problem** (symptom + which builds hit it)
- **Root cause**
- **Change** (file paths, config keys)
- **Tests**
- **Status** (implemented / partial / deferred)

## Config conventions established

Patterns that worked and should be copied for new builds (with examples).

## Known limitations (deferred)

From GAPS_LOG entries not yet implemented — prioritized P1–P3.

## Implications for next batches

- SARS-CoV-2 (volume, subsampling)
- Production phylo profiles (masks, clades, UFBoot)
- Flu live runs
- Any pipeline features worth designing before scaling further

## Appendix: open biological inputs

Maintainer decisions still needed (references, masks, clade TSVs, subsample targets).
```

**Quality bar for the learnings file:**

- Every major code change in git history for this effort appears in § Code adjustments compendium.
- Every GAPS_LOG entry is either reflected here or explicitly marked obsolete/superseded.
- Patterns are stated generally ("NCBI synthetic constructs…") not only as one-off anecdotes.
- Actionable: a new contributor could read only this file and avoid repeating the same mistakes.

---

## Required output format

In addition to writing `builds/MULTI_BUILD_LEARNINGS.md`, produce a structured **review report** (in chat or a separate `builds/MULTI_BUILD_REVIEW.md` if the user prefers a file) with these sections:

Produce a structured review document with these sections:

### Executive summary

3–5 sentences: overall assessment, biggest wins, biggest gaps, recommendation (merge as-is / merge with fixes / do not merge).

### Scorecard

| Dimension | Score (1–5) | Summary |
|-----------|-------------|---------|
| Plan completeness | | |
| Biological / config accuracy | | |
| Build file quality | | |
| Pipeline fix quality | | |
| Code standards | | |
| Test coverage | | |
| Documentation | | |
| Operational evidence | | |
| Maintainability | | |
| Empirical synthesis | | |
| **Overall** | | weighted average or holistic |

### Empirical synthesis summary

Short narrative (not just a score): top 3 cross-pathogen insights, top 3 recurring footguns,
and whether flexpipe is ready to scale to high-volume or production-grade builds without
further structural changes. Point to sections in `builds/MULTI_BUILD_LEARNINGS.md`.

### Per-build status audit

Table comparing BUILD_ROSTER claims to your independent assessment:

| Build | Roster says | Verified | Gaps / corrections |
|-------|-------------|----------|-------------------|
| `zikv-brazil` | | | |
| … | | | |

### Findings

Group by severity:

**Critical** — wrong biology, broken wiring, false success claims, missing tests for safety-critical fixes  
**Major** — incomplete deliverables, doc inaccuracy, fragile patterns  
**Minor** — style, missing NOTES, non-blocking open questions  
**Positive** — things done well (be specific)

Each finding: `ID`, severity, location (file:line or build), evidence, recommended action.

### Pipeline fix audit

For each fix in PIPELINE_FIXES / GAPS_LOG with `Status: Implemented`:

| Fix | Correct? | Tested? | Minimal? | Notes |
|-----|----------|---------|----------|-------|

### Test & CI report

- Commands run and pass/fail counts
- Builds missing from parametrized lists
- Suggested new tests (prioritized)

### Open questions for maintainer

Only **residual** questions not already answered in BUILD_ROSTER/GAPS_LOG — blocking vs non-blocking.

### Recommended follow-ups

Ordered list (P0–P3) of next actions: config calibrations, live flu runs, production phylo profile, shared geocode cache, etc. Cross-link to § Implications in `builds/MULTI_BUILD_LEARNINGS.md`.

### Tracking-doc coherence check

| Doc | Complete? | Accurate? | Gaps vs MULTI_BUILD_LEARNINGS |
|-----|-----------|-----------|-------------------------------|
| BUILD_ROSTER.md | | | |
| GAPS_LOG.md | | | |
| PIPELINE_FIXES.md | | | |
| builds/*/NOTES.md | | | |

Note any contradictions between tracking docs and the synthesis file; recommend which doc should be canonical for each type of information going forward.

---

## Evaluation principles

- **Evidence over narrative** — trust git and tests over session summaries.
- **Distinguish first-pass from production** — header-only clades, `JC`, uncalibrated masks are acceptable if documented.
- **No grade inflation** — a 5 requires excellence, not mere completion.
- **Be constructive** — every critical/major finding should have an actionable fix.
- **Synthesis over duplication** — `MULTI_BUILD_LEARNINGS.md` generalizes; GAPS_LOG stays the raw gap register; PIPELINE_FIXES stays the fix changelog. Avoid three copies of the same paragraph.
- **Do not modify pipeline code** during this review unless the user explicitly asks you to fix issues afterward. **Do write** `builds/MULTI_BUILD_LEARNINGS.md` (and optionally `builds/MULTI_BUILD_REVIEW.md`).

---

## Start here

1. Read the tracking docs, per-build `NOTES.md`, and recent git history (`git log --oneline`, `git log -p` for `flexpipe/`, Snakefiles, `tests/`).
2. Run verification commands and record results.
3. Inspect each in-scope build directory and relevant pipeline diffs.
4. Work through deep-dive §8 (cross-pathogen synthesis) and write **`builds/MULTI_BUILD_LEARNINGS.md`**.
5. Produce the structured review report in the required output format above.
6. If `MULTI_BUILD_LEARNINGS.md` reveals GAPS_LOG or PIPELINE_FIXES are stale, note corrections in the review — do not silently rewrite those files unless asked.
