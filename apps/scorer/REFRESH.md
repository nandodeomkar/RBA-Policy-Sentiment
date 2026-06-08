# Refresh runbook — add a new RBA decision (FR-009)

When the RBA publishes a new monetary-policy **decision media release**, this is the
checklist to score it and get it live. The job is **manually triggered** and offline
(no always-on service) — today the maintainer is Claude, run on request, but it is
written so any maintainer can follow it.

> **The one rule that matters most:** if scoring fails, **do not push.** The site is
> static-first — the last good `data/*.json` stays live until you commit new data, so a
> failed run simply means today's deploy doesn't happen (NFR-007). Nothing breaks.

Design: [M2/M3 §6](../../docs/superpowers/specs/2026-06-08-rba-m2-m3-design.md) · scorer
internals: [M0 design](../../docs/superpowers/specs/2026-06-06-rba-m0-scorer-design.md).

---

## Prerequisites (one-time)

From `apps/scorer/`:

```powershell
uv sync                       # core + dev deps (no PyTorch)
uv sync --extra transformer   # add PyTorch + the transformer component
Copy-Item .env.example .env   # then put a real ANTHROPIC_API_KEY in .env
```

The `score` step makes **one live Claude call per *new* decision** (model
`claude-haiku-4-5-20251001`, `temperature 0`); the existing decisions are cache hits and
make no call. The transformer currently runs the interim **fed-stance** model (FOMC-RoBERTa
is access-gated — see the engine note below).

---

## The refresh

Run steps 1–4 from `apps/scorer/`, step 5 from `apps/web/`.

1. **Ingest the new decision** — idempotent; no API key needed.
   ```powershell
   uv run rba-scorer ingest
   ```
   Fetches + parses any decisions not already in `data/decisions.json` (date, title, source
   URL, outcome, cash-rate target). Re-running when nothing is new is a clean no-op. Only
   short evidence quotes are ever persisted — never full statement text (NFR-011).

2. **Score it.**
   ```powershell
   uv run rba-scorer score
   ```
   - The existing decisions carry the current `engine_version`, so they are **reused
     byte-identical** (compute-once). Only the **new** decision is scored, with one live
     Claude call (then cached) + the lexicon + the transformer.
   - Writes `data/scores.json` and refreshes `data/engine_version.json`.
   - **If it exits non-zero, stop here** (see *If something fails* below) — `scores.json`
     is left untouched, so the live site is unaffected.

3. **Sanity-check.**
   ```powershell
   uv run pytest
   ```
   No network, no model downloads — should stay green.

4. *(optional) Re-score nothing to confirm determinism* — running `score` again should
   report all decisions reused and leave `data/scores.json` byte-identical.

5. **Sync + build the web data** — from `apps/web/`:
   ```powershell
   node scripts/sync-data.mjs
   ```
   Copies `data/decisions.json` + `data/scores.json` into `apps/web/data/` and rebuilds
   `apps/web/data/scores.csv`. (`apps/web/data/` is gitignored — Vercel regenerates it from
   the committed repo-root `data/` on deploy. This local run is just to preview.)

6. **Preview locally** *(optional but recommended)* — from `apps/web/`:
   ```powershell
   python -m http.server 8000   # open http://localhost:8000
   ```
   Confirm the new decision shows on the chart + table with a correct breakdown, cash rate,
   source link, and (once the overlay is toggled on) a cash-rate step.

7. **Commit + deploy.** Commit and push to `main`; **Vercel auto-deploys**.
   Commit **these** paths:
   - `data/decisions.json`, `data/scores.json`, `data/engine_version.json` — the published contract.
   - `apps/scorer/cache/llm/*.json` — the new decision's cached LLM response (short phrases +
     rationale only; this is what makes re-runs deterministic and is safe to commit).

   Do **not** commit `apps/scorer/.cache/raw/` (gitignored — it holds full page text) or
   `apps/web/data/` (gitignored — generated on deploy).

8. **Verify live** — once Vercel finishes, open the production site and confirm the new
   decision is on the chart and the full record, its breakdown + source link are correct,
   and the cash-rate overlay steps to the new target. Done.

---

## Rules

- **Routine refresh = same `engine_version`.** Same models, same lexicon, same reconciliation
  → only new decisions get scored; every existing score is reused unchanged. This is the
  normal case and keeps the dataset reproducible (NFR-002).
- **Changing a model is NOT a routine refresh.** Swapping the interim `fed-stance` transformer
  for an RBA-specific (or the gated FOMC-RoBERTa) model, or editing the lexicon / prompt /
  reconciliation, changes the composite `engine_version` and triggers a **full re-score of all
  decisions**. Do it deliberately as its own change (run `score --force` if needed), not folded
  into a decision-day refresh, and note the version bump.
- **If something fails, don't push.** A missing/invalid API key or model aborts the batch
  *before* writing (exit 1) and leaves `data/scores.json` intact. A single un-fetchable page is
  skipped-and-logged and the rest of the batch still writes. Either way: investigate, re-run,
  and only commit once the data looks right. The last good data stays live throughout (NFR-007).

## Engine note (current)

`engine-2026.06-57c7cd6e` = lexicon `lex-v1` + LLM `claude-haiku-4-5-20251001:llm-p1` +
transformer `fed-stance` + `reconcile-v1`. The full record is in
[`data/engine_version.json`](../../data/engine_version.json).

<!-- M3 forward marker: once FR-012 lands, the `score` step will also generate each
decision's cached, descriptive `tone_summary` (versioned separately from engine_version).
Add that substep here when it ships — it does not change anything above. -->
