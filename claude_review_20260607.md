# Claude `/plan` prompt — review Codex hardening & DENV builds (2026-06-07)

Use this document as the **full instruction set** for a Claude session on branch `feat/major_code_review`.

---

## Mission

Assess the work between:

- **Base (Claude / Sprint 5):** `700463e4327b52f4d1f4697d35974c33bbeabb81`
- **Tip (Codex session):** `be3f6e4f6e90b82cc89eeddbe2ea64366e4a6d00`

That range implements two related efforts:

1. **Hardening for scheduled/unattended runs** — motivated by `codex_review.md` (independent review of workflow-level risks: cwd-dependent paths, mask flags, coordinate cache collisions, trait state explosion, shell quoting, fail-fast behaviour, manifest provenance, etc.).

2. **Empirical multi-build expansion** — motivated by `plan_builds.md`: scaffold builds, run them, discover pipeline gaps, fix the pipeline (not just build YAML). DENV1–4 Brazil scaffolds were created; DENV3/4 were validated with live end-to-end runs.

Your job has three parts:

1. **Assess** code quality, consistency, and completeness of changes in `700463e..be3f6e4`.
2. **Implement** targeted fixes you believe are necessary (do not stop at a report-only review).
3. **Plan** a repeatable continuation workflow: minimalist builds → run → discover → fix → test.

Ask questions when biological defaults, build priorities, or scope tradeoffs are unclear.

---

## Commit range (read in order)

```bash
git log --oneline 700463e..be3f6e4
git diff --stat 700463e..be3f6e4
git diff 700463e..be3f6e4 --name-only
```

Expected commits (~4):

| Commit | Theme |
|--------|--------|
| `d797553` | Harden flexpipe for scheduled builds — path resolution, geo cache, hues, manifest, fail-fast ingest, Snakefile quoting, `docs/service_contract.md`, integration tests |
| `08da419` | DENV1–4 Brazil builds + pipeline adaptations (lineage parser, traits cap, hierarchical colours, phylo traits module, Pathoplexus query params, etc.) |
| `2686073` | Removed `AGENTS.md`, `CLAUDE.md`, `HARDENING_CHANGELOG.md`, `codex_review.md` from repo |
| `be3f6e4` | Removed empirical `NOTES.md` from denv builds |

**Important:** Several review/planning docs were deleted in this range. Recover context from git if missing on disk:

```bash
git show 08da419:codex_review.md
git show d797553:HARDENING_CHANGELOG.md
git show 08da419:CLAUDE.md
git show 08da419:builds/denv3-brazil/NOTES.md   # live-run notes before be3f6e4
```

Untracked locally (may exist in workspace): `plan_builds.md`, `plan_traits_colors_lineages.md`, `builds/BUILD_ROSTER.md`, `builds/GAPS_LOG.md`, `builds/PIPELINE_FIXES.md`.

---

## Context documents (read first)

| Document | Purpose |
|----------|---------|
| `codex_review.md` (recover from git) | Original findings H1–H5, M1–M10, hardening roadmap |
| `docs/service_contract.md` | Service execution contract added in hardening |
| `plan_builds.md` (if present) | Prompt that started DENV empirical builds |
| `plan_traits_colors_lineages.md` (if present) | Traits/colours/lineage workstream spec |
| `builds/denv3-brazil/config.yaml`, `builds/denv4-brazil/config.yaml` | Reference builds (smaller/faster for testing) |
| `builds/yfv-brazil/`, `builds/rsv-global/` | Existing reference builds |
| `tests/integration/test_ingest_wiring.py`, `tests/integration/test_phylo_wiring.py` | Wiring test patterns |

---

## Part 1 — Assessment (deliver a written review)

Compare `700463e..be3f6e4` against `codex_review.md` findings and the empirical-build goals in `plan_builds.md`.

### Hardening checklist (from codex review)

Verify each was addressed adequately; note gaps:

- [ ] **H1** cwd-independent build paths → resolved in `snakemake_resolved.yaml` / `load_config()`
- [ ] **H2** optional `mask_sites` / BED flags not rendered when empty
- [ ] **H3** coordinate cache keys include parent context (no city-name collisions)
- [ ] **H4** stable hues (hash or persistent cache; siblings do not shift when categories added)
- [ ] **H5** Snakemake shell quoting (`{input:q}`, etc.)
- [ ] **M1–M10** (files.cache, NCBI email, zero-record fail-fast, manifest hashing, thread/cores, ViralQC runner, QC summary reasons, run_date validation, …)

### DENV / multi-build checklist

- [ ] Four DENV scaffolds under `builds/denv*-brazil/` are coherent and consistent
- [ ] DENV3/DENV4 runnable (recover run notes from `08da419` if `NOTES.md` removed)
- [ ] Integration tests cover denv3/denv4 ingest + phylo dry-runs
- [ ] Lineage parser (`flexpipe/curate/lineage_parser.py`) is correct and tested
- [ ] Traits cap (`flexpipe/phylo/traits.py`) prevents TreeTime state explosion
- [ ] Hierarchical colours (`flexpipe/colors/hues.py`, `scheme.py`) behave as intended
- [ ] Deleting `CLAUDE.md` / `codex_review.md` — was essential content moved to README/docs or lost?

### Code quality

- Consistency with existing flexpipe patterns (pydantic config, workdir isolation, CLI entry points)
- Test coverage for new modules; no duplicated logic between Snakefiles and Python
- Over-engineering vs minimal fixes
- Breaking changes for YFV / RSV scaffolds

**Output:** `REVIEW_700463e_be3f6e4.md` with summary, findings by severity, “fixed in this session” vs “deferred”, and recommended next steps.

---

## Part 2 — Implement necessary fixes

After assessment, implement **minimal, high-value** corrections. Prioritize:

1. Regressions or incomplete hardening items (especially H1, H2, fail-fast paths)
2. Test gaps for denv3/denv4 wiring
3. Documentation recovery: restore or merge essential content from deleted `CLAUDE.md` / `codex_review.md` into `README.md` or `docs/` (do not leave agents/users without onboarding docs)
4. Build config inconsistencies across DENV1–4
5. Any bugs found by running:

```bash
conda run -n nextstrain pytest
conda run -n nextstrain pytest -m integration
conda run -n nextstrain ruff check .
conda run -n nextstrain black --check .
conda run -n nextstrain mypy flexpipe/ --ignore-missing-imports
```

Optional live smoke (network + ViralQC required):

```bash
flexpipe-run --config builds/denv4-brazil/config.yaml \
  --workdir /tmp/flexpipe-denv4-review \
  --run-date 2026-06-07 \
  --stage ingest \
  --cores 4
```

Prefer **denv3-brazil** and **denv4-brazil** for live tests (smaller datasets).

### Constraints

- Minimize scope; no unrelated refactors
- Preserve workdir isolation
- Do not commit untracked planning markdown unless asked (`plan_*.md`, `builds/GAPS_LOG.md`, etc.)
- Ask before large architectural changes

---

## Part 3 — Plan continuation of empirical build workflow

Design a **repeatable loop** for the remaining pathogens in `plan_builds.md` (and future builds):

```
scaffold minimalist build → dry-run → live ingest (if feasible) → record gaps →
minimal pipeline fix + test → update BUILD_ROSTER / PIPELINE_FIXES
```

Deliver `plan_builds_continuation.md` including:

1. **Minimal build template** — smallest file set under `builds/<name>/` to exercise a new pathogen
2. **Priority queue** — which builds next (smaller/faster first; DENV1–4 done; ~9 pathogens remain in original registry)
3. **Standard commands** — dry-run, live E2E, auspice view (parameterized by build name)
4. **Gap taxonomy** — config-only | pipeline bug | missing biological input | out-of-scope
5. **CI strategy** — which builds get integration dry-run tests vs manual-only
6. **Definition of “minimalist build”** — placeholder reference OK? header-only clades? lightweight phylo (JC, ufboot=0) for first pass?

Reference [flexpipe-RSV](https://github.com/thalesbermann/flexpipe-RSV/tree/main) for Brazil-focal subsampling and colour hierarchy patterns where relevant.

---

## Deliverables

| # | Deliverable |
|---|-------------|
| 1 | `REVIEW_700463e_be3f6e4.md` — assessment |
| 2 | Code fixes + tests (as needed) |
| 3 | `plan_builds_continuation.md` — next-phase workflow |
| 4 | Update `builds/PIPELINE_FIXES.md` or `README.md` if docs were lost in `2686073` |
| 5 | All CI checks green |

---

## Suggested execution order

1. Read diff and key files (`git diff 700463e..be3f6e4`; recover deleted docs from git)
2. Run test suite; note failures
3. Write assessment doc
4. Implement fixes (highest severity first)
5. Re-run tests
6. Write continuation plan
7. Post summary: what was reviewed, what was fixed, what is next

---

## How to invoke

Paste into Claude Code:

```
/plan Read and execute claude_review_20260607.md on branch feat/major_code_review.
Start with Part 1 assessment, then Part 2 fixes, then Part 3 continuation plan.
Ask questions before large changes.
```

Optional modifiers:

- **Review only:** add “Assessment and continuation plan only; do not implement fixes unless blocking.”
- **Restore docs:** add “Restore essential content from deleted codex_review.md and CLAUDE.md into committed docs.”
