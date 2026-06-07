# RBA Policy Sentiment — Milestones 2 & 3 Engineering Design

| Field | Value |
| ----- | ----- |
| Status | Draft — awaiting owner review |
| Date | 2026-06-08 |
| Owner | Omkar |
| Scope | **M2 (Context + currency)** and **M3 (Depth)** — additions on top of the deployed M1 static site + M0 scorer. |
| Fulfils | FR-004, FR-009, NFR-007/008 (M2); FR-010, FR-012 (M3) |
| Source of truth | [PRD.md](../../prd/rba-policy-sentiment/PRD.md) · [TASKS.md](../../prd/rba-policy-sentiment/TASKS.md) · [HANDOFF.md](../../prd/rba-policy-sentiment/HANDOFF.md) · [M0 design](./2026-06-06-rba-m0-scorer-design.md) · [M1 design](./2026-06-07-rba-m1-frontend-design.md) |

---

## 1. Scope & context

This designs **Milestones 2 and 3** as incremental additions to the live (pre-launch) M1 site. The site is **static-first and data-agnostic**: it reads the precomputed JSON the scorer produces and renders whatever is there. These milestones are being built **pre-launch** while the M0 accuracy labels are outsourced to independent experts — nothing here changes the launch gate (NFR-004); the whole site stays no-index until that passes.

**Requirements implemented:**
- **M2 — Context + currency:** FR-004 (cash-rate overlay), FR-009 (maintainer manual-refresh runbook), NFR-007/008 (decision-day resilience).
- **M3 — Depth:** FR-010 (date zoom/filter, shareable via URL), FR-012 (auto plain-language tone summary of the latest decision).

**Build order:** **M2 first, then M3** (M2 is the higher-priority context layer; M3's items are both P2/post-launch).

---

## 2. Decisions locked during brainstorming (2026-06-08)

1. **Cash-rate overlay = toggle, off by default.** A second y-axis (right, %) with a stepped cash-rate line; a "Cash rate" checkbox in the existing filter row adds/removes it. Default view stays tone-only. (Considered: always-on, and rescaling onto the −1…+1 axis — both rejected; a separate axis is honest and dismissible.)
2. **Keep both the Year dropdown and the new date slider.** The **dataZoom slider is the canonical date window**; the Year dropdown is a shortcut that sets it. Dragging the slider to a non-year range flips the dropdown back to "All". (Owner choice: keep both rather than replace.)
3. **FR-009 = a documented runbook the maintainer executes** (today: Claude, on request). No CI automation now. (Considered: a one-click GitHub Action — rejected for now: needs an API-key secret and the transformer is awkward/slow in CI; YAGNI at ~8 decisions/year. Re-evaluate at launch.)
4. **FR-012 = an LLM-generated tone summary**, produced **offline + cached**, **strictly descriptive**, **versioned separately** from the score `engine_version`. The existing deterministic hero headline is the **fallback**.
5. **Tone summary shows on the hero AND in every decision's detail panel** — so it's generated for all decisions, not just the latest.
6. **Shareable URL = query params** for the date window + outcome toggles + cash-rate toggle, plus the **existing `#<decision-id>` anchor** for the selected decision.
7. **Non-goals reaffirmed:** the tone summary is descriptive only — **no forecasting, no advice**; decision releases only; RBA only; **never persist/republish full statement text** (the summary is derived from already-persisted scores + short evidence phrases, not a fresh read of full text); free-tier only.

---

## 3. Architecture overview

Same two-part system; these milestones touch a focused set of files.

```
apps/web/
├─ index.html        # + "Cash rate" toggle in the filter row; + dataZoom container; (no structural change)
├─ core.js           # + 2nd y-axis & stepped cash-rate series; + dataZoom; + URL view-state (encode/decode); + tone summary in detail
├─ app.js            # + wire cash-rate toggle, slider↔table↔URL sync, Year↔slider interplay, parse-URL-on-load
├─ styles.css        # + slider/toggle styling
└─ data/scores.json  # (synced) now carries tone_summary per decision
apps/scorer/
├─ src/rba_scorer/score/…   # + tone-summary generation step (reuses the pinned/cached LLM client)
└─ REFRESH.md        # NEW — the FR-009 maintainer runbook
data/scores.json     # canonical scorer output; gains tone_summary (+ version)
```

**No new data files, no deploy-config change.** `scores.json` gains one field (backward-compatible).

---

## 4. Data contract changes

- **`scores.json`** — each decision gains:
  - `tone_summary: string` — a 1–2 sentence plain-language description of the decision's tone.
  - `tone_summary_version: string` — e.g. `"summary-p1:claude-haiku-4-5-20251001"`, versioned **independently** of `engine_version` so re-wording the summary does not churn any score.
- **`engine_version`** — unchanged (the summary is presentational, not part of the score).
- **`decisions.json`** — unchanged (`cash_rate_target` is already present per decision).
- **`scores.csv`** — unchanged. The CSV stays the numeric, citable dataset; the prose summary is a UI affordance, not a dataset column (keeps FR-008's columns stable).
- **Backward compatibility:** the frontend renders `tone_summary` when present and **falls back to the deterministic `buildHeadline`** when absent, so the site never breaks on older data.

---

## 5. M2 · Cash-rate overlay (FR-004)

Frontend-only; the data already exists.

- **Second y-axis** (`yAxisIndex: 1`, right side, units `%`), range from a pure helper `cashRateAxisBounds(rows)` (nice min/max with padding; e.g. 0 → ~5%). Independent of the −1…+1 stance axis, so neither distorts the other.
- **Stepped line series** (ECharts `step: "end"`) plotting `[ts, cash_rate_target]` for each decision in the current window, on `yAxisIndex 1`, styled **clearly secondary** to the stance line (muted/neutral hue, thinner, below the stance line's z-order). Markers are not needed — the table carries the exact values.
- **Toggle:** a **"Cash rate" checkbox** added to the existing `.filters` row, **off by default**. On → add the axis + series; off → remove the series and hide the right axis. Reuses the established filter-wiring pattern.
- **Tooltip:** when on, the cash-rate line shows its target % at that date; the stance tooltip is unchanged (it already prints "cash rate X%").
- **URL:** the toggle state is part of the shareable view-state (`rate=1`, §8).
- **Accessibility (NFR-005):** the full-record table already has a **Cash rate** column — the accessible equivalent is already present, no new burden.

---

## 6. M2 · Manual-refresh runbook (FR-009)

The deliverable is **`apps/scorer/REFRESH.md`** — a maintainer checklist for adding a newly published decision. Today the maintainer is Claude (run on request); it is written so any maintainer can follow it.

**Steps:**
1. `uv run rba-scorer ingest` — idempotent; fetches/parses the new decision into `data/decisions.json`. No API key.
2. Ensure `ANTHROPIC_API_KEY` is set in `apps/scorer/.env`, and `uv sync --extra transformer` for the full ensemble.
3. `uv run rba-scorer score` — scores the new decision with a **live LLM call** (the existing 64 are cache hits) and generates its `tone_summary`. Writes `data/scores.json`.
4. `uv run pytest` — sanity check.
5. From `apps/web/`: `node scripts/sync-data.mjs` (regenerates the synced JSON + `scores.csv`).
6. Commit the new `data/*.json`, the new decision's LLM cache files, and push to `main` → **Vercel auto-deploys**.
7. **Verify live:** the new decision appears on the chart + table; its breakdown, source link, and tone summary are correct.

**Rules documented in the runbook:**
- A **routine refresh keeps the same `engine_version`** (same models, same config) — only new decisions get new scores; existing ones are cache-identical.
- **Changing a model** (e.g. swapping the interim `fed-stance` transformer for an RBA model) is a **full re-score** of all decisions and a deliberate `engine_version` bump — a separate event, not a routine refresh.
- **If scoring fails** (API down, parse error), **do not push** — the last good data stays live (NFR-007).

---

## 7. M2 · Decision-day resilience (NFR-007/008)

Largely satisfied by the existing architecture; this milestone **documents and confirms** it rather than adding machinery.

- **Static-first:** the site serves precomputed JSON from Vercel's CDN. A failed scoring job means we simply don't push — **the last good data stays live**. No always-on dependency to fall over.
- **Spikes (NFR-008):** decision-day traffic (~8×/year) is absorbed by static CDN delivery; nothing to scale.
- **Fetch-failure fallback (M1):** already in place — a graceful message linking to the RBA decisions page.
- **No fake "awaiting" state:** the hero always shows the latest **scored** decision, which is the honest state between meetings. (We deliberately do **not** track a future-meeting calendar — that drifts toward the forecasting non-goal.)

---

## 8. M3 · Date zoom + shareable URL (FR-010)

- **dataZoom slider** (ECharts `slider` type, bound to the time x-axis) beneath the chart. Dragging the handles sets any custom date window; only that range renders, and the **full-record table filters to the same window** (so chart and table stay in lockstep).
- **Year dropdown kept** as a quick shortcut: selecting a year sets the slider window to that year; "All years" resets it to the full range. **The slider is the canonical window state** — dragging it to a range that isn't a single calendar year sets the dropdown back to "All". Outcome toggles + **Reset** are unchanged (Reset → full range, all outcomes, cash-rate off, cleared URL).
- **Shareable URL:** query params encode the view —
  - `from`, `to` — ISO dates of the window (omitted when full range)
  - `out` — csv of enabled outcomes (e.g. `hike,hold`; omitted when all)
  - `rate` — `1` when the cash-rate overlay is on
  - plus the existing **`#<decision-id>`** anchor for the open detail panel.
  - On load: parse → set slider, toggles, overlay, and open the decision. On change: `history.replaceState` (no history spam). Encode/decode are **pure helpers** (`encodeViewState` / `decodeViewState`) in `core.js`, **unit-tested** round-trip.
- **Accessibility:** the dataZoom slider is keyboard-operable; the table remains the screen-reader truth view, filtered to the window.

---

## 9. M3 · LLM tone summary (FR-012)

**Scorer side:**
- A new step generates, per decision, a **1–2 sentence descriptive `tone_summary`**, reusing the existing **pinned/cached** LLM client (the same determinism machinery as the LLM scorer).
- **Input = already-persisted signals only** — the decision's date, outcome, net + sub-scores, confidence, and its **short evidence phrases**. It does **not** re-read or store full statement text (licensing NFR-011 stays intact), and it ties the summary to the computed score.
- **Prompt guardrails:** describe the tone the statement struck (net lean + the dominant dimension + what drove it) in plain language. **Explicitly no forecasting, no advice, no prediction** of future decisions or rates. `temperature: 0`.
- **Caching + versioning:** keyed by `prompt_version` + input hash → byte-identical re-runs (NFR-002). Stored as `tone_summary` + `tone_summary_version`, **separate from `engine_version`**.
- **Cost:** ~64 one-time calls (then cached); +1 per new decision at refresh.

**Frontend side:**
- **Hero:** show `tone_summary` when present; **fall back to the deterministic `buildHeadline`** otherwise. (The deterministic version stays as the safety net and for any unscored-summary state.)
- **Detail panel (`renderDetail`):** add the decision's `tone_summary` as a lead plain-language line above the breakdown — same fallback behaviour.

---

## 10. `core.js` / module changes

- **`buildStanceChart`** — add `yAxis[1]` + the stepped cash-rate series (toggleable); add the `dataZoom` slider; emit a window-change callback so `app.js` can sync the table + URL.
- **New pure helpers (unit-tested):**
  - `cashRateAxisBounds(rows)` → `{min, max}` for the right axis.
  - `encodeViewState(state)` / `decodeViewState(search)` → URL query ⇄ `{from, to, out[], rate}`.
- **`renderDetail`** — insert the `tone_summary` line (with fallback).
- **`app.js`** — wire the cash-rate checkbox; sync slider ⇄ table ⇄ URL; the Year ⇄ slider interplay; parse the URL on load.
- **File-size note:** `core.js` is the established home for chart/table/detail logic; these additions keep functions small and single-purpose. If `core.js` later grows unwieldy, splitting a dedicated chart module is a clean follow-up — **not** done now (no need yet).

---

## 11. States, accessibility & performance

- Cash-rate **off by default**; toggling is instant (client-side). dataZoom is client-side and keyboard-accessible; the table mirrors the window. `prefers-reduced-motion` respected (existing). URL state makes any view shareable.
- **Performance (NFR-001):** unchanged fetch profile; dataZoom and the overlay are client-side. `tone_summary` adds ~64 short strings to `scores.json` (currently ~404 KB) — negligible, well within budget.

---

## 12. Testing

- **Unit (`node --test`):** `encodeViewState`/`decodeViewState` round-trip (incl. empty/full-range omission); `cashRateAxisBounds`. Existing helper tests unaffected.
- **Scorer (`pytest`):** `tone_summary` generation is deterministic from the cache; a structural guard that generation consumes only persisted signals (no full-text dependency); cache hit/miss behaviour.
- **Manual QA (append to the web README checklist):** cash-rate toggle on/off in light/dark/mobile; slider drag updates chart + table + URL; opening a shared URL restores window + toggles + selected decision; tone summary on hero + detail; deterministic fallback when `tone_summary` is absent.

---

## 13. Deployment / runbook

- **No deploy-config change.** Vercel still builds `apps/web` (`sync-data.mjs`) and serves static.
- **`apps/scorer/REFRESH.md`** is the FR-009 deliverable; tone-summary generation runs offline as part of `score`.

---

## 14. Scope & non-goals

- **In:** FR-004, FR-009, NFR-007/008 (M2); FR-010, FR-012 (M3).
- **Out / reaffirmed non-goals:** no forecasting or advice (the tone summary is descriptive only); decision media releases only; RBA only; **never persist/republish full statement text** (summary derives from persisted scores + short evidence phrases); free-tier only; no accounts; no future-meeting calendar; no other central banks.

---

## 15. Risks & open items

| # | Risk / item | Mitigation |
| - | ----------- | ---------- |
| R-1 | Year dropdown ⇄ slider interaction confusing | Slider is canonical; Year is a shortcut that sets it; dragging a custom range → dropdown shows "All"; Reset clears everything. |
| R-2 | Tone summary drifting toward advice/forecasting | Strict descriptive-only prompt; `temperature 0`; cached + reviewed; derived from scored signals, not free text. |
| R-3 | `core.js` growth | Keep added functions small/single-purpose; a chart-module split is a clean future option, not now. |
| R-4 | Summary (re)generation needs the API key | Same as scoring; covered by the refresh runbook; cached so it's one-time per decision. |
| R-5 | `engine_version` vs `tone_summary_version` confusion | Versioned separately and documented; the summary never affects a score. |

---

## 16. Traceability

| Requirement | Where addressed |
| ----------- | --------------- |
| FR-004 cash-rate overlay | §5 |
| FR-009 manual refresh | §6 |
| NFR-007/008 resilience | §7 |
| FR-010 date zoom + share | §8 |
| FR-012 tone summary | §9 |
| NFR-001 performance | §11 |
| NFR-002 reproducibility (summary cache) | §9 |
| NFR-011 licensing (no full text) | §9, §14 |
