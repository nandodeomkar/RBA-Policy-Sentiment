# RBA Policy Sentiment — Milestone 0 Implementation Plan

| Field | Value |
| ----- | ----- |
| Status | Ready to execute |
| Date | 2026-06-06 |
| Design | [2026-06-06-rba-m0-scorer-design.md](../specs/2026-06-06-rba-m0-scorer-design.md) |
| Scope | M0 only — ingestion + reconciled hybrid ensemble + benchmark gate |

Dependency-ordered. Each step lists its **done** condition. 🧑 marks a **human-in-the-loop checkpoint** (something only you can do). Phases B–E build in the agreed iterative order so accuracy is measured as components are added.

> **Branching:** all code work happens on a `feat/m0-scorer` branch (the spec/plan docs live on `main`). Opened at the start of Phase A.

---

## Phase A — Scaffolding & tooling

1. **Python package skeleton** — `apps/scorer/` with `src/rba_scorer/` (src layout), `pyproject.toml` (uv-managed), `ruff` + `pytest` config, `.env.example` (`ANTHROPIC_API_KEY=`), and a short `apps/scorer/README.md` with run commands.
   - *Done:* `uv sync` installs; `uv run pytest` runs (zero tests is fine); `uv run ruff check .` passes.
2. **CLI entrypoint** — `cli.py` exposing `ingest`, `score`, `benchmark`, `export` subcommands (stubs that wire up logging + config).
   - *Done:* `uv run rba-scorer --help` lists all four subcommands.
3. **Output skeleton** — create `data/` contract dirs and `data/benchmark/`; commit `.gitkeep`s where needed.
   - *Done:* directory layout matches design §2.
4. **Record commands in CLAUDE.md** — fill the "Commands" gap noted in the existing CLAUDE.md (build/test/lint/run for the scorer).
   - *Done:* CLAUDE.md has real, runnable commands.

## Phase B — Ingestion (FR-001, NFR-006, NFR-011)

5. **Raw fetch + cache layer** — `httpx` fetch with on-disk snapshot to `apps/scorer/.cache/raw/` (gitignored). Re-runs read cache.
   - *Done:* fetching a page twice hits the network once.
6. **Decisions index parser** — enumerate decision releases from 2020+ → list of `(date, url)`. 🧑 *quick confirmation of the live page structure happens here.*
   - *Done:* returns the expected count of post-2020 decisions.
7. **Media-release parser** — per release → `date`, `title`, `source_url`, `outcome{action, change_bps}`. Fails loud on missing fields (R-003).
   - *Done:* parses all cached releases; a deliberately corrupted fixture raises a clear error.
8. **Cash-rate-target ingester** — parse RBA's cash-rate file → `cash_rate_target` per decision; cross-validate `outcome` against the target change.
   - *Done:* every decision has a target; a hold/hike/cut mismatch raises.
9. **`decision` writer** — atomic, idempotent upsert → `data/decisions.json`. No full text persisted.
   - *Done:* re-running ingestion produces no diff and no duplicates; grep confirms no statement body in the file.
10. **Parser tests** — trimmed/synthetic fixtures for index, release, and cash-rate parsing.
    - *Done:* `pytest` green; fixtures contain no full statement text.

## Phase C — Benchmark harness (NFR-004) — built before scoring, per the iterative strategy

11. **Draft `RUBRIC.md` + `labels.csv` template** — 5-point net scale, bucket definitions, worked examples; one row per decision id, `net_label` blank.
    - *Done:* rubric committed; template has every decision id pre-filled, label column empty.
12. **Split + metrics + gate + report** — seeded ⅓ test / ⅔ dev split; within-one-bucket agreement (primary) + Spearman (corroborating); `benchmark_report.{md,json}` with per-decision residuals and per-component agreement. Pre-registered gate logic.
    - *Done:* unit-tested on toy labels; dev/test isolation verified; metrics correct on known inputs.

## Phase D — Scoring components (iterative; measure agreement after each)

13. **Component interface + `score` writer** — shared `net + sub_scores` contract on [−1,+1]; `data/scores.json` writer.
    - *Done:* a fake component round-trips through the writer and schema-validates.
14. **Lexicon scorer (v1)** — curated, dimension-tagged hawkish/dovish lexicon (seeded from central-bank literature), negation handling, evidence emission. → **measure dev agreement (lexicon-only).**
    - *Done:* unit tests incl. negation; baseline agreement number recorded in the report.
15. **LLM scorer** — Claude Haiku, `temperature=0`, sentence-level structured output (dimension/polarity/intensity + short phrases + rationale), disk cache keyed by `hash(model_id+prompt+text)`. 🧑 *needs `ANTHROPIC_API_KEY` for the first live run.* → **measure dev agreement (lexicon+LLM).**
    - *Done:* determinism test passes (score twice → identical); cache stores no full text; agreement recorded.
16. **Transformer scorer** — FOMC-RoBERTa (pinned revision), per-sentence → net only, behind an interface mocked in unit tests. 🧑 *first run downloads the model / needs `torch`.* → **measure dev agreement (full ensemble).**
    - *Done:* mock-based unit tests pass; one marked integration test runs the real model; agreement recorded.
    - *2026-06-07 — superseded by the [pluggable-model design](../specs/2026-06-07-rba-pluggable-transformer-models-design.md):* FOMC-RoBERTa became gated, so the slot now runs the non-gated interim **fed-stance** model (model-agnostic adapter + registry). Mock + live integration tests pass; all 64 re-scored. Dev-agreement measurement stays deferred with the accuracy gate (NFR-004, owner labels).
17. **Reconciliation** — equal-weight net blend, sub-scores from dimension-aware pair, confidence = 1 − normalized disagreement, evidence merge/dedupe.
    - *Done:* unit tests for blend, confidence, and evidence merge on synthetic component outputs.
18. **Engine version + compute-once** — composite `engine_version`; skip re-scoring unless version changes or `--force`; write `data/engine_version.json`.
    - *Done:* re-running `score` is a no-op; bumping any component version triggers re-score.

## Phase E — Gate, outputs & close

19. **Full pipeline run** — `ingest → score → export`; produce `scores.json`, `exports/scores.csv`, `engine_version.json`.
    - *Done:* CSV columns match FR-008; every score has all FR-011 fields.
20. **Label + validate the gate** 🧑 — you fill `labels.csv`; iterate lexicon/prompt against **dev** residuals only; lock and score the **test** set once.
    - *Done:* held-out within-one-bucket agreement **≥85%** (Spearman reported alongside). **This is the hard gate.**
21. **Provenance + licensing audit** — every score links to its `rba.gov.au` source; confirm no full statement text anywhere in the committed tree.
    - *Done:* automated check passes for both.
22. **Finalize** — update CLAUDE.md commands, methodology-seed notes from the benchmark report, open a PR for `feat/m0-scorer`.
    - *Done:* M0 exit criteria (design §12) all checked.

---

## Human-in-the-loop summary (what I'll need from you)

| When | What |
| ---- | ---- |
| Step 15 | `ANTHROPIC_API_KEY` in `apps/scorer/.env` (for the first live LLM run) |
| Step 16 | OK to install `torch` + download FOMC-RoBERTa locally on first run |
| Step 20 | You hand-label the corpus in `labels.csv` using the rubric (~an hour) |
| Step 20 | Joint review of the gate result before we call M0 done |

Everything else (scaffolding, parsers, scorer code, tests, harness) I can build and test on my own, using cached fixtures and mocked model calls so the suite runs without network or credentials.
