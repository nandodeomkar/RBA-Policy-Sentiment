# RBA Policy Sentiment — Milestone 2 Implementation Plan

| Field | Value |
| ----- | ----- |
| Status | Ready to execute |
| Date | 2026-06-08 |
| Design | [2026-06-08-rba-m2-m3-design.md](../specs/2026-06-08-rba-m2-m3-design.md) (§5–§7) |
| Scope | **M2 — Context + currency:** cash-rate overlay (FR-004), manual-refresh runbook (FR-009), decision-day resilience (NFR-007/008). M3 (date zoom + tone summary) is stubbed at the end. |
| Fulfils | FR-004, FR-009, NFR-007, NFR-008 |

Dependency-ordered. Each step lists its **done** condition. 🧑 marks a **human-in-the-loop checkpoint** (something only you can do — deploy, or a real new decision).

> **Why this is small:** M2 adds **no new data files and no data-contract change** — `cash_rate_target` already ships per decision in `decisions.json` (and is in every `joinDecisions` row as `r.decision.cash_rate_target`). The overlay is therefore **frontend-only**; the runbook + resilience items are **documentation + confirmation** of behaviour the static-first architecture already has. I can build and verify all of it locally against the synced data — **no API key or model in the loop**. You're only needed to deploy (and, for the full FR-009 proof, whenever the next real RBA decision is published).

> **Branching:** all M2 work (this plan + code) is on **`feat/m2-m3`**, already branched off `main` (which carries M0 + M1). The design doc is already committed here. The site stays **no-index** throughout — M2 is built pre-launch and **does not touch the M0 accuracy gate** (NFR-004); launch is still gated on that.

---

## Phase A — Cash-rate overlay (FR-004)

Frontend-only. Goal (FR-004 acceptance): *when the user enables the rate series, cash-rate target steps render aligned to the same time axis.* Off by default; a separate right-hand axis so neither line distorts the other (design §5).

1. **Pure helper + unit test** — add `cashRateAxisBounds(rows)` to `core.js` (export it alongside the other pure helpers): returns `{min, max}` for the right axis from the decisions' `cash_rate_target`, with nice rounding + headroom (e.g. floor at 0, round the top up to a clean step → ~0–5%). Computed over **all rows** so the axis stays stable as Year/Outcome filters change. Add cases to `tests/core.test.mjs`: normal range, single value, empty rows.
   - *Done:* `node --test` green; bounds are stable and sensibly padded across the 0.10–4.35% span.
2. **Second axis + stepped series in `buildStanceChart`** — in `core.js` (the chart is `core.js:228–335`): make `yAxis` an array — keep the stance axis (`[-1,+1]`, `yAxis[0]`) and add `yAxis[1]` (right side, units `%`, range from `cashRateAxisBounds`, its own gridlines off so it doesn't clutter the stance grid). Add a stepped line series (`type:"line"`, `step:"end"`, `yAxisIndex:1`) plotting `[ts, cash_rate_target]` per in-window decision, styled **clearly secondary** (muted hue, thinner, lower `z` than the stance line). Drive visibility from a `rate` flag in the chart state, **off by default**: when off, `yAxis[1].show=false` and the series carries empty data; when on, show the axis + populate. Extend `tooltip()` (`core.js:266`) so a hover on the cash-rate series prints the date + target % (the stance tooltip already prints "cash rate X%", unchanged).
   - *Done:* with the flag forced on, the stepped cash-rate line + right `%` axis render aligned to the same time axis across all 64; forced off, the chart is byte-for-byte the current tone-only view.
3. **Toggle control + wiring** — add a **"Cash rate" checkbox** to the `.filters` form (`index.html:99–114`, e.g. a third `.filter-field` before Reset), reusing the existing `.check` style. Thread it through the existing filter flow: extend `setupFilters` (`core.js:198`) to accept an optional `rateCheck` — on change it re-applies, and **Reset unchecks it** (Reset → all years, all outcomes, cash-rate **off**, per design §8). In `app.js`'s `onApply` (`app.js:163`) read the checkbox and pass the flag into `chart.update(year, types, rateOn)` (extend `update` at `core.js:322` to take the flag and toggle the axis/series).
   - *Done:* the checkbox adds/removes the overlay live; Reset clears it; toggling does not disturb the Year/Outcome filters or the stance line.
4. **Styling + accessibility pass** — confirm the checkbox reads correctly in **light and dark** and at ~375px (reuse `.check`; minor tweak only if it crowds the row); the overlay hue is legible (not colour-only — it's a distinct stepped line + its own axis). The full-record table already has a **Cash rate** column (`index.html:139`, `core.js:348`) — the accessible equivalent already exists, no new burden (NFR-005).
   - *Done:* overlay legible in both themes + mobile; checkbox keyboard-operable; table remains the screen-reader truth view.

## Phase B — Manual-refresh runbook + resilience (FR-009, NFR-007/008)

Documentation + confirmation. No code change to the scorer.

5. **Write `apps/scorer/REFRESH.md`** (the FR-009 deliverable) — a maintainer checklist to add a newly published decision, per design §6. Steps: `uv run rba-scorer ingest` (idempotent, no key) → set `ANTHROPIC_API_KEY` + `uv sync --extra transformer` → `uv run rba-scorer score` (new decision = live LLM call; the existing 64 are cache hits) → `uv run pytest` → from `apps/web/` `node scripts/sync-data.mjs` → commit the new `data/*.json` + the new decision's LLM cache files + push to `main` → **Vercel auto-deploys** → verify live. Document the **rules:** a routine refresh **keeps the same `engine_version`** (only new decisions get scored; existing are cache-identical); **changing a model is a deliberate full re-score + `engine_version` bump**, a separate event; **if scoring fails, do not push** (last good data stays live).
   - *Done:* `REFRESH.md` is followable by any maintainer; the `engine_version` / re-score rules are explicit. *(M3 note: the `score` step will also emit `tone_summary` once FR-012 lands — leave a one-line forward marker, don't pre-build it.)*
6. **Dry-run the runbook** — execute steps 1–5 of `REFRESH.md` against the current corpus: `ingest` (no new decision → no-op), `score` (all 64 cache hits → byte-identical `scores.json`), `pytest` green, `sync-data.mjs` regenerates the synced JSON + `scores.csv` with no diff. This proves every step except onboarding a genuinely new decision.
   - *Done:* the runbook runs clean end-to-end with **zero data diff** (confirms idempotence + reproducibility, NFR-002); the only unproven path is a real new decision (step 10 🧑).
7. **Document + confirm decision-day resilience (NFR-007/008)** — add a short **"Resilience"** note (in `apps/web/README.md` near the QA checklist, cross-linked from `REFRESH.md`) recording what the architecture already guarantees (design §7): static-first CDN delivery → a failed scoring job means *we simply don't push*, last good data stays live; decision-day spikes (~8×/year) absorbed by static delivery; the **fetch-failure fallback** already in `app.js` (`showError`, `app.js:129`) links to the RBA decisions page; **no fake "awaiting" state** (the hero always shows the latest *scored* decision — the honest between-meetings state; no future-meeting calendar, which would drift toward the forecasting non-goal). Then **confirm the fallback still works** (temporarily point a fetch at a missing file → graceful message, not a broken page).
   - *Done:* the resilience guarantees are written down and the fetch-fail fallback is verified intact.

## Phase C — QA, deploy, close

8. **Manual QA** — append M2 rows to the web QA checklist and run them: cash-rate toggle on/off in **light/dark/~375px**; Reset clears the overlay; tooltip shows the target % on the rate line; Year/Outcome filters still drive chart **and** table together with the overlay on; deep-link + CSV unaffected; no console errors.
   - *Done:* the checklist passes locally.
9. **Deploy** 🧑 — I prepare the merge of `feat/m2-m3` → `main`; **you confirm**, then Vercel auto-deploys (per the existing live-deploy setup; no config change). Site stays **no-index**.
   - *Done:* production serves the cash-rate toggle; the overlay renders live; free-tier (NFR-009) unchanged. *(I'll handle the git steps and explain them plainly.)*
10. **Validate FR-009 on a real decision** 🧑 *(deferred — opportunistic)* — at the **next published RBA decision**, follow `REFRESH.md` for real: ingest + score it, sync, deploy, and confirm it appears on the chart + table with a correct breakdown, source link, and cash rate. This is the only part of FR-009 that a dry-run can't fully prove.
    - *Done:* a genuinely new decision flows through the runbook and shows up live — closing FR-009's acceptance criterion.
11. **Finalize** — tick **FR-004**, **FR-009** (structurally; note the real-decision validation as opportunistic), **NFR-007/008** in [TASKS.md](../../prd/rba-policy-sentiment/TASKS.md) M2; note any QA-checklist additions in `apps/web/README.md`; open/update the PR for `feat/m2-m3`.
    - *Done:* M2 exit criteria met — *cash-rate overlay live; the manual refresh process documented and working*; PR opened.

---

## M3 (later — designed, not built in this pass)

Per the same design doc (§8–§9), once M2 lands:

- **Date zoom + shareable URL** (FR-010) — an ECharts `dataZoom` slider as the canonical date window (Year dropdown becomes a shortcut that sets it); the table filters to the same window; view-state encoded in query params (`from`/`to`/`out`/`rate`) + the existing `#<id>` anchor; pure `encodeViewState`/`decodeViewState` helpers, round-trip unit-tested.
- **LLM tone summary** (FR-012) — offline + cached, strictly descriptive, **versioned separately** from `engine_version` (`tone_summary` + `tone_summary_version` added to `scores.json`, backward-compatible); shown on the hero and in every detail panel, with the deterministic `buildHeadline` as the fallback. **This is the step that adds the tone-summary substep to `REFRESH.md`.**

## Human-in-the-loop summary (what I'll need from you)

| When | What |
| ---- | ---- |
| Step 9 | Confirm the merge to `main` for deploy (I prep the git; Vercel auto-deploys) |
| Step 10 | At the next real RBA decision, give the word to run `REFRESH.md` for real |
| (optional) | A visual spot-check of the overlay at any point — say the word |

Everything else — the helper + tests, the chart overlay, the toggle wiring, the runbook, the dry-run, and the resilience confirmation — I build and verify locally against the synced data, no credentials or models required.
