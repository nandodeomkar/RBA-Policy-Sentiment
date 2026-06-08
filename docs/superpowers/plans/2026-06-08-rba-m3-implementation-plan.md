# RBA Policy Sentiment — Milestone 3 Implementation Plan

| Field | Value |
| ----- | ----- |
| Status | Ready to execute |
| Date | 2026-06-08 |
| Design | [2026-06-08-rba-m2-m3-design.md](../specs/2026-06-08-rba-m2-m3-design.md) (§8–§9) |
| Scope | **M3 — Depth (post-launch):** date zoom/filter + shareable URL (FR-010); LLM tone summary (FR-012). Builds on the deployed M0 scorer + M1/M2 site. |
| Fulfils | FR-010, FR-012 (both P2) |

Dependency-ordered. Each step lists its **done** condition. 🧑 marks a **human-in-the-loop checkpoint**. Unlike M2, one piece (FR-012's tone summaries) needs a **live LLM run** to populate data — but I can build and unit-test *all* the code without a key (the LLM client is behind an injectable seam), and the frontend renders against a fixture; you're only needed to run the one-time generation and to deploy.

> **Branching:** continues on **`feat/m2-m3`** (already carries M2, now merged to `main`). The design is committed. Build **FR-010 first** (frontend-only, fully autonomous), then FR-012.

> **No launch-gate change.** M3 is post-launch depth, built pre-launch behind no-index; it does not touch NFR-004.

---

## Data contract change (FR-012)

`scores.json` — each decision **gains two fields**, both backward-compatible:
- `tone_summary: string` — a 1–2 sentence plain-language description of the decision's tone.
- `tone_summary_version: string` — e.g. `"summary-p1:claude-haiku-4-5-20251001"`, **versioned independently of `engine_version`** so re-wording the summary never churns a score.

`engine_version` is **unchanged** (the summary is presentational). `scores.csv` is **unchanged** (the prose summary is a UI affordance, not a dataset column — FR-008's columns stay stable). The frontend renders `tone_summary` when present and **falls back to the deterministic `buildHeadline`** when absent, so old data never breaks.

---

## Phase A — Date zoom + shareable URL (FR-010)

Frontend-only, no key. The current windowing is **Year-only** (`buildStanceChart` sets `xAxis` min/max from `yearWindow()`, `core.js:262`). FR-010 makes a **date window** the canonical state, with Year as a shortcut.

1. **Pure helpers + unit tests** — add to `core.js` (exported, `node --test`):
   - `encodeViewState(state)` / `decodeViewState(search)` — `{from, to, out[], rate}` ⇄ a query string. Omit `from`/`to` at full range, `out` when all outcomes on, `rate` when off. **Round-trip tested**, including the empty/default case (→ empty query) and partial combos.
   - `windowForYear(year, rows)` → `{from, to}` for a calendar year (and `null/null` for "all"); `yearForWindow(from, to)` → a year string iff the window exactly matches one calendar year, else `null` (drives the Year↔slider sync).
   - *Done:* helpers cover the §8 rules; round-trip is green for full-range, year, custom-range, outcome-subset, and rate-on.
2. **dataZoom slider in `buildStanceChart`** — add an ECharts `dataZoom` (`type:"slider"`, bound to the time `xAxis`, keyboard-operable) beneath the chart. Replace the year-based `xAxis` min/max mechanism with a **window state `[from,to]`** that the slider drives; render **all** in-outcome points and let the zoom clip the view (drop the `inYear` filter from `linePoints`/`ratePoints`/`markerSeries`; markers still respect the Outcome toggles). The **cash-rate overlay rides along** unchanged (same x-axis). Emit an `onWindowChange(from, to)` callback so `app.js` can sync the table + URL.
   - *Done:* dragging the slider re-windows the chart (stance line, markers, and cash-rate overlay) live; full 64 render at full range; `prefers-reduced-motion` still honored.
3. **Year ⇄ slider interplay + Reset** — the **slider is canonical.** Selecting a Year sets the window to that year (`windowForYear`); dragging the slider to a range that isn't exactly one calendar year sets the Year dropdown back to **"All"** (`yearForWindow`). **Reset** → full range, all outcomes on, **cash-rate off**, cleared URL (extend the existing reset in `setupFilters`, `core.js:198`).
   - *Done:* Year sets the slider; a custom drag flips Year to "All"; Reset returns everything to default and clears the query string.
4. **Table sync to the window** — the full-record table filters to the **same `[from,to]`** as the chart (so chart and table stay in lockstep), combined with the Outcome toggles. The live status line counts the windowed rows. The table remains the screen-reader truth view (NFR-005).
   - *Done:* narrowing the slider narrows the table identically; the empty-window state shows the existing message.
5. **Shareable URL** — in `app.js`: on any view change, `history.replaceState` with `encodeViewState` (no history spam); on load, `decodeViewState(location.search)` → set the slider window, Outcome toggles, cash-rate overlay, then open the `#<decision-id>` decision (the existing hash anchor is kept, `app.js:193`). Order: apply view-state → then hash.
   - *Done:* copying the URL after zoom/filter/overlay/select and reopening it **restores that exact view** (window + outcomes + overlay + open decision); verified in preview.
6. **QA (FR-010)** — keyboard operate the slider; light/dark; ~375px; shareable-URL round-trip; Reset; deep-link still works.
   - *Done:* checklist passes locally; FR-010 acceptance met (*only that range renders and is shareable via URL*).

## Phase B — Tone summary: scorer generation (FR-012)

Autonomous to build + test (injected fake completer); the **live run** is step 10 🧑.

7. **Summary module** — new `apps/scorer/src/rba_scorer/score/summary.py`, mirroring `llm.py`'s determinism machinery but **separate**: its own `SUMMARY_PROMPT_VERSION`, `temperature 0`, an **injectable `completer` seam**, and a **committed** cache dir `apps/scorer/cache/summary/` keyed by `hash(summary_prompt_version + input_signals)`. The input is **only already-persisted signals** — date, outcome, net + sub-scores, confidence, and the short evidence phrases — **never full statement text** (licensing NFR-011 stays intact; ties the summary to the computed score). Prompt guardrails: describe the tone struck (net lean + the dominant dimension + what drove it) in plain language, **explicitly no forecasting / no advice / no prediction**.
   - *Done:* `summary_for(record)` returns a cached 1–2 sentence string; `tone_summary_version()` = `summary-p1:<model_id>`; a cache hit makes no call; over-long output is bounded.
8. **Wire into `run_score`** — after the scoring loop (`runner.py:143`), a **separate pass** attaches `tone_summary` + `tone_summary_version` to each record, **gated on the summary version** (compute-once on its own axis: reuse when the stored version matches and signals are unchanged → cache hit; regenerate only when missing/stale). Independent of `engine_version`, so a routine re-score stays byte-identical and reused decisions keep their summaries. Add a `--without-summaries` flag (parallel to `--without-transformer`) so the lexicon+LLM-only / no-key path still runs.
   - *Done:* `score` emits the two new fields per decision; a re-run with no change is a no-op cache hit; with no key + `--without-summaries` it still completes (fields simply absent).
9. **Scorer tests (`pytest`)** — deterministic generation from the cache; a **structural guard** that generation consumes only the persisted signals (no full-text/`source_url`-fetch dependency); cache hit/miss; the version-gating reuse path; backward-compat (records without the fields still load).
   - *Done:* `uv run pytest` green, no network/key.
10. **Generate for all 64 (live, one-time)** 🧑 — with `ANTHROPIC_API_KEY` set: `uv run rba-scorer score` makes ~64 one-time summary calls (then cached), writing `tone_summary` into `data/scores.json`; commit the new `apps/scorer/cache/summary/*.json` (short prose only — licensing-clean, like the LLM cache).
    - *Done:* all 64 carry a sensible, descriptive `tone_summary`; re-running is a byte-identical no-op (NFR-002).

## Phase C — Tone summary: frontend display (FR-012)

Autonomous; build against a fixture (one record with `tone_summary`, one without) so it works **before and after** step 10.

11. **Hero + detail render with fallback** — hero: show `tone_summary` when present, else the deterministic `buildHeadline` (adjust `headlineHtml`, `app.js:84`). Detail panel: add the `tone_summary` as a **lead plain-language line** above the breakdown (`renderDetail`, `core.js:367`), same fallback. Keep the "not financial advice" framing intact.
    - *Done:* with `tone_summary` present it shows on the hero **and** every detail panel; with it absent, the deterministic sentence shows — no visual breakage either way; verified in preview against the fixture, then real data.

## Phase D — Runbook, QA, deploy, close

12. **Update `REFRESH.md`** — replace the M3 forward-marker with the real substep: the `score` step now also generates each new decision's `tone_summary` (live call, cached); commit the new `cache/summary/*.json` alongside the LLM cache. Note `tone_summary_version` vs `engine_version` (re-wording the summary never re-scores).
    - *Done:* the runbook reflects the tone-summary step; a maintainer can refresh end to end.
13. **Manual QA + finalize** — full pass (slider keyboard/light/dark/mobile, shareable URL, overlay interplay, tone summary on hero + detail + fallback, no console errors); tick **FR-010 / FR-012** in [TASKS.md](../../prd/rba-policy-sentiment/TASKS.md); update the web QA checklist; deploy 🧑 (merge `feat/m2-m3` → `main`, stays no-index) and verify live.
    - *Done:* M3 exit criteria met — *date zoom/filter; latest-decision plain-language summary* — live (no-index); PR/merge done.

---

## Risks & notes

- **dataZoom replaces year-windowing** (step 2) — touches the M2 chart code (`inYear` → window state). The cash-rate overlay rides the same x-axis, so it needs no special handling; just verify it zooms with the rest.
- **Tone summary drifting toward advice/forecasting** — strict descriptive-only prompt, `temperature 0`, cached + reviewable, derived from scored signals (not free text). Spot-check the 64 at step 10.
- **`engine_version` vs `tone_summary_version`** — versioned and cached **separately**; the summary never affects a score. Documented in `REFRESH.md`.
- **`core.js` growth** — keep added functions small/single-purpose; a dedicated chart-module split stays a clean future option, **not** done now.

## Human-in-the-loop summary

| When | What |
| ---- | ---- |
| Step 10 | Set `ANTHROPIC_API_KEY` and run the one-time summary generation (~64 cached calls) — or hand it to me if the key is in `apps/scorer/.env` |
| Step 13 | Confirm the merge to `main` for deploy (I prep the git; Vercel auto-deploys) |
| (optional) | A visual spot-check of the slider or the summaries at any point |

Everything else — the FR-010 slider + URL state + helpers/tests, the summary module + wiring + scorer tests, and the frontend display against a fixture — I build and verify locally, no credentials required.
