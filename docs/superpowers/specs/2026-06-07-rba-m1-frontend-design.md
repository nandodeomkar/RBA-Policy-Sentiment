# RBA Policy Sentiment — Milestone 1 Frontend Engineering Design

| Field | Value |
| ----- | ----- |
| Status | Draft — awaiting owner review |
| Date | 2026-06-07 |
| Owner | Omkar |
| Scope | **Milestone 1 front end** — the static site that consumes the M0 file contract. **First build (slice 1) = the home page.** Full M1 architecture is designed here so later surfaces drop in without re-architecting. |
| Fulfils | The right half of the file contract from the [M0 design](./2026-06-06-rba-m0-scorer-design.md) |
| Source of truth | [PRD.md](../../prd/rba-policy-sentiment/PRD.md) · [TASKS.md](../../prd/rba-policy-sentiment/TASKS.md) · [HANDOFF.md](../../prd/rba-policy-sentiment/HANDOFF.md) · UI reference: [RBA-Tracker](https://github.com/nandodeomkar/RBA-Tracker) (live: rba-tracker.vercel.app) |

---

## 1. Scope & context

This is the engineering design for **Milestone 1 — Public MVP**, the static front end. The heavy lifting was M0 (the offline scorer); this milestone is **static-first** — the site reads the precomputed JSON the scorer already produced and renders it. No always-on service.

**This spec designs all of M1 but builds it in two slices:**
- **Slice 1 (this build):** the **home page** end-to-end — "Latest decision" hero, stance-over-time chart, full-record table, the per-decision **granular breakdown** panel, footer + disclaimers, light/dark, data sync, tests.
- **Slice 2 (fast-follow, still M1):** methodology page, plain-language explainer, CSV export.

**Requirements implemented across M1:** FR-003 (stance chart), FR-005 (statement detail), FR-006 (explainer — slice 2), FR-007 (methodology — slice 2), FR-008 (CSV — slice 2), FR-011 (full granular breakdown), NFR-001 (performance), NFR-003 (transparency surface), NFR-005 (accessibility), NFR-006 (provenance display), NFR-009 (free-tier), NFR-010 (privacy analytics), NFR-011 (licensing display). **Deferred to later milestones:** FR-004 cash-rate overlay (M2), FR-010 zoom/share (M3), FR-012 auto tone summary (M3).

**Engine-paused note.** The owner is researching engine improvements in parallel; the live scores are the current **lexicon + LLM** output. The site is **data-agnostic**: when the engine is finished and re-scores, the JSON is regenerated and the site re-reads it — no frontend change. This is why the breakdown UI renders **whatever components exist** rather than a fixed three.

---

## 2. Decisions locked during brainstorming (2026-06-07)

1. **Stack: vanilla static HTML/CSS/JS + vendored Apache ECharts** — mirror the owner's RBA-Tracker exactly (no build, no framework, no `package.json` runtime deps).
   - **PRD reconciliation:** [PRD §10](../../prd/rba-policy-sentiment/PRD.md) names "Next.js," but it qualifies that as *"mirroring the owner's existing tracker"* — and the existing tracker is **vanilla static**, not Next.js. No acceptance criterion in §8/§9 mandates a framework; the requirements only demand **static-first**, **free-tier**, and the **design language**. Vanilla maximises sibling consistency (direct reuse of the tracker's tokens, ECharts theme, table/footer/theme-toggle/analytics), simplicity, and true static delivery. Next.js (static-export) and Astro (islands) were considered and set aside as unnecessary for a static data site.
2. **First build = the home page** (see §1). Full M1 architecture designed up front.
3. **Data delivery = fetch the precomputed JSON contract** (not a hand-edited `data.js` global). Honors the PRD's "serves precomputed JSON/CSV" and keeps the scorer the single source of truth. A small **sync step** copies the repo-root `data/` into the deployed web root.
4. **The granular breakdown lives inline on the home page** — a detail panel updated on selection and **deep-linkable via `#<decision-id>`** — not a separate per-decision route. (Owner-approved; also seeds M3's shareable URLs.)
5. **N-component rendering** — the detail panel iterates over whatever components are present (today `lexicon` + `llm`; a `transformer` card appears automatically when the engine adds it).
6. **Net orientation:** negative = **dovish**, positive = **hawkish**, `0` = neutral; fixed **symmetric [−1, +1]** axis (honest scale).
7. **Plain-language buckets are deterministic** (templated from score thresholds — §6). FR-012's LLM-generated summary stays in M3.

---

## 3. Architecture overview

Two halves connected by a file contract; M0 built the left half, M1 builds the right.

```
RBA/
├─ apps/
│  ├─ scorer/                 # Python batch job (M0 — paused)
│  └─ web/                    # ← THIS MILESTONE (static site)
│     ├─ index.html           # home page (slice 1)
│     ├─ methodology.html     # slice 2
│     ├─ styles.css           # tracker tokens + sentiment components
│     ├─ core.js              # window.RBACore: helpers + render fns (dual browser/Node export)
│     ├─ app.js               # page wiring: load data → hero, chart, table, detail
│     ├─ vendor/echarts.min.js# vendored (copied from the tracker)
│     ├─ data/                # decisions.json + scores.json (SYNCED; gitignored)
│     ├─ scripts/sync-data.mjs# copies repo-root data/*.json → apps/web/data/
│     ├─ tests/core.test.mjs  # node --test on pure helpers
│     ├─ vercel.json
│     ├─ README.md            # runbook (sync · local preview · deploy · QA checklist)
│     └─ favicon.svg, robots.txt, og-image.png
├─ data/                      # PUBLISHED OUTPUT = the contract (produced by the scorer)
│  ├─ decisions.json
│  ├─ scores.json
│  └─ exports/scores.csv      # consumed in slice 2 (FR-008)
└─ docs/                      # PRD, specs (this file)
```

**Module boundaries (kept small and single-purpose):**
- **`core.js`** — all reusable logic: pure helpers + the chart/table/detail renderers + theme/filter/reveal wiring. Exposed on `window.RBACore` for the browser **and** `module.exports` for `node --test` (so the pure logic is testable headlessly).
- **`app.js`** — thin page glue only: fetch the data, build the hero, hand the rest to `core.js`. (Same split as the tracker's `core.js` / `app.js`.)
- **`styles.css`** — the tracker's token system verbatim plus the new sentiment components.
- **`scripts/sync-data.mjs`** — the only coupling to the scorer side.

---

## 4. Data flow & the contract consumed

```
scorer (paused)  →  repo-root data/{decisions,scores}.json  →  sync-data.mjs  →  apps/web/data/  →  fetch()  →  render
```

**Shapes consumed** (produced by M0; unchanged here):
- `decisions.json` — array of `{ id, date, title, source_url, outcome:{action,change_bps}, cash_rate_target }`.
- `scores.json` — object keyed by decision `id`: `{ net, sub_scores:{inflation,growth,employment}, confidence, components:{<name>:{net,version,sub_scores,…}}, reconciliation:{method,weights,disagreement}, evidence_phrases:[{text,polarity,dimension,source[]}], engine_version, source_url, scored_at }`.

**Join & order.** Load both, **join by `id`**, sort chronologically. The **latest** entry drives the hero. Current corpus: **64 decisions, 2020-02-04 → 2026-05-05** (outcomes: 42 hold / 16 hike / 6 cut).

**Concrete latest decision (hero example, real data):** `2026-05-05` — **hike +0.25% → 4.35%**, net **+0.309 (hawkish)**, confidence **0.69**, sub-scores inflation **+0.40** / growth **−0.31** / employment **0.00**, 16 evidence phrases, components `lexicon` + `llm`, engine `engine-2026.06-d8acadec`.

**Title caveat.** Titles vary by era — `"Statement by Philip Lowe, Governor: …"` (pre-2025) vs `"Statement by the Monetary Policy Board: …"` (2025+). The hero headline **must not assume a Governor name**; phrase as "the RBA" / "the Board."

**Sync & sources of truth.** `data/` at the repo root (committed, scorer-owned) is canonical. `sync-data.mjs` copies `decisions.json` + `scores.json` into `apps/web/data/`, which is **gitignored and generated** (never hand-edited). Local preview needs a static server (`python -m http.server`) because `fetch()` does not work over `file://`. Vercel: root = `apps/web`, build command runs the sync.

---

## 5. `core.js` module API

**Reused from the tracker (largely verbatim):** `parseDate`, `ts`, `yearOf`, `formatDate`, `formatDateShort`, `fmtRate`, `fmtPP`, `escapeHtml`, `prefersReducedMotion`, `countUp`, `initTheme`, `setupFilters`, `revealOnLoad`, and the resize-aware ECharts lifecycle.

**Adapted:** `describeOutcome(decision)` → `{glyph,label,dir}` for cut ▼ / hold ● / hike ▲ (the tracker's `describe`, renamed for clarity).

**New (pure, unit-tested):**
- `stanceBucket(net)` → `{key,label}` using §6 thresholds.
- `confidenceBucket(conf)` → `{key,label,pct}`.
- `joinDecisions(decisions, scores)` → sorted array of `{decision, score}` (skips any decision without a score, logs a warning).
- `signed(x, dp)` → `"+0.31"` / `"−0.31"` (true minus glyph, tabular).

**New (render fns):**
- `buildStanceChart(elId, rows, cfg)` — §8.
- `renderRecordTable(tbodyEl, rows)` — §10.
- `renderDetail(containerEl, row)` — §9.

**Dual export footer:**
```js
var RBACore = { /* … */ };
if (typeof window !== "undefined") window.RBACore = RBACore;
if (typeof module !== "undefined" && module.exports) module.exports = RBACore;
```

---

## 6. The stance model in the UI

- **Orientation:** negative = dovish, positive = hawkish, `0` = neutral.
- **Scale:** fixed **[−1, +1]**, `0` centred. Observed max ≈ 0.90, so the headroom is honest. **Never truncate or rescale** to dramatise.
- **Plain-language buckets** (`stanceBucket`, applied to net and each sub-score):

  | net range | label |
  | --------- | ----- |
  | `≤ −0.60` | Strongly dovish |
  | `(−0.60, −0.15]` | Dovish |
  | `(−0.15, +0.15)` | Broadly neutral |
  | `[+0.15, +0.60)` | Hawkish |
  | `≥ +0.60` | Strongly hawkish |

- **Confidence** (`confidenceBucket`): `≥0.80` high · `[0.50, 0.80)` moderate · `<0.50` low — shown as a word **and** the %. Low confidence is surfaced prominently (it is the product's honesty signal), never hidden.
- **Honest visuals (inherited guardrails):** encode stance by **position + signed number + label**, never colour alone; symmetric axis from −1…+1; sub-scores use the same scale so they're comparable.
- Thresholds are a documented judgement call (restated on the methodology page in slice 2) and live in one place in `core.js` for easy tuning.

---

## 7. Home page layout & components (top → bottom)

1. **Topbar** — wordmark "RBA Policy Sentiment" + light/dark toggle (reuse `initTheme`, key `rba-sentiment-theme`).
2. **Hero — "Latest decision"** (FR-005 partial):
   - Eyebrow: `Latest decision · {formatDate}`.
   - **Headline (deterministic template, hedged):** *"On {date}, the RBA's tone read as **{stance bucket}**{, leaning {dominant sub-dimension}} while it {held the cash rate steady / raised the cash rate by {Δ} / lowered the cash rate by {Δ}} to **{rate}%**."* The "leaning …" clause appears only when one sub-dimension is the clear largest with `|sub| ≥ 0.15`; it is omitted otherwise.
   - The big **net stance** on a Dovish↔Hawkish track (the centrepiece number).
   - **Sub-score panel:** inflation / growth / employment as three compact diverging bars.
   - **Confidence** chip (word + %).
   - One short **evidence quote** (the first `evidence_phrases` item whose polarity matches the net sign; fallback: the first item).
   - "Read the RBA statement →" (→ `source_url`).
3. **"The record" section** — heading + one explanatory line; **filters**: Year select + outcome toggles (Cut ▼ / Hold ● / Hike ▲, all on) + Reset + live status (reuse `setupFilters`). Filters drive chart **and** table together.
4. **Stance chart** (§8) + figcaption naming the table as the accessible equivalent.
5. **Detail panel** (§9) — hidden until a decision is selected (or a hash is present on load).
6. **Full-record table** (§10).
7. **Footer** — three blocks: **What these scores mean** (dovish↔hawkish, sub-dimensions, confidence; **"This is not financial advice."**) · **How it's built** (one-paragraph method + `engine_version`; link to methodology in slice 2) · **Sources** (RBA decisions + cash-rate links; "every figure links to its RBA source"; **"An independent project — not an official RBA product."**).
8. `<noscript>` fallback + Vercel cookieless analytics (reuse the tracker's snippet).

---

## 8. Stance chart (FR-003)

ECharts (SVG renderer), adapted from the tracker's `buildChart`:
- **X:** time (decision dates). **Y:** net stance, fixed **[−1, +1]**, with an emphasised `0` centreline; axis ends labelled **Dovish** (−1) / **Hawkish** (+1).
- **Series:** a line through each decision's net value, with **markers on the line shape-coded by outcome** (▲ hike / ● hold / ▼ cut) — so one view shows both the *tone trajectory* and *what the Board did*. Shapes (not colour) carry outcome; a legend is the key.
- **Tooltip:** date · stance label + value · the three sub-scores · outcome + resulting cash rate · confidence.
- **Interaction:** click a marker → open the detail panel + set `location.hash = #<id>`. Year filter zooms the x-window; outcome toggles filter chart + table.
- **M2 hook:** leave a clean second-y-axis seam so the cash-rate overlay (FR-004) drops in without restructuring.
- **Fallback:** if ECharts fails to load, the chart container shows "The chart could not load — the full record is in the table below" (the table is the truth view).

---

## 9. Detail panel (FR-005 + FR-011) — the transparency centrepiece

Rendered by `renderDetail(container, row)`; **deep-linkable** (`#<id>`); on load, if `location.hash` matches a decision, open it.

Contents:
- **Header:** date · outcome (glyph+label) · resulting cash rate · "Read the RBA statement →".
- **Reconciled result:** net stance (track) + three sub-scores + confidence (word + %, with disagreement called out when high).
- **Per-component cards — iterate over `score.components`** (today `lexicon`, `llm`; `transformer` auto-renders when present): each card shows the component's net + sub-scores + `version`; **lexicon** lists its `matched_terms`; **llm** shows its `rationale` and evidence list.
- **Reconciliation:** `method`, `weights`, `disagreement`.
- **Evidence phrases:** `evidence_phrases[]` as labelled chips — **polarity** (dovish/hawkish) + **dimension** + **source component(s)**.
- **Provenance footnote:** `engine_version` + `scored_at`.

**Licensing (NFR-011), enforced in the UI:** render **only the short evidence quotes** — never full statement text — and link every view to the canonical `rba.gov.au` source (NFR-006).

---

## 10. Full-record table (NFR-005 — the accessible fallback)

The screen-reader-truth equivalent of the chart; a first-class element, newest first. Columns: **Meeting · Outcome · Change · Cash rate · Net stance · Confidence · Source.** Net stance shows the signed value + bucket label (+ a small inline track). Rows are **clickable and keyboard-operable** → open the detail panel. Horizontal scroll on mobile. Empty-filter state: "No decisions match these filters."

---

## 11. States, accessibility & performance

- **States:** loading skeleton (hero + chart) → **fetch-failure** message linking to the RBA decisions page → empty-filter → `<noscript>`. An "awaiting update" note pattern (as in the tracker) is available for between-meeting gaps.
- **Accessibility (NFR-005, WCAG 2.1 AA):** single `<h1>`, logical heading order, skip link, visible focus states, AA contrast (inherited tokens), **outcome/stance legible without colour** (shape + signed number + text), `prefers-reduced-motion` honored, comfortable touch targets at ~360px, and the chart-has-a-table-equivalent guarantee.
- **Performance (NFR-001):** a single one-time `fetch` of the two JSON files (gzipped well under budget; SVG ECharts). Target p95 load ≤ 2.5s, interactions ≤ 100ms. *Risk:* `scores.json` is the larger payload — see §15.
- **Privacy analytics (NFR-010):** reuse Vercel's cookieless snippet; events — chart interaction, detail open, (slice 2) CSV download + methodology view, and page-load timing for the §3 guardrail.

---

## 12. Testing

- **Unit (`node --test`, zero deps):** the pure helpers — `stanceBucket`, `confidenceBucket`, `joinDecisions`, `signed`, `describeOutcome`, date/rate formatting — via the dual export. This is the bulk of the logic risk.
- **Manual QA checklist (in README):** light/dark, ~375px mobile, full keyboard pass, no-JS, fetch-failure, empty filter, deep-link to a decision.
- **Deferred:** a Playwright smoke test (not in slice 1; revisit if the surface grows).

---

## 13. Deployment

- **`vercel.json`:** root directory `apps/web`; build command runs `node scripts/sync-data.mjs` (copies `../../data/*.json` → `./data/`); static output.
- `apps/web/data/` is **gitignored and generated** — never committed.
- **README runbook:** sync → local static server → deploy → the QA checklist. Free-tier only (NFR-009).

---

## 14. Scope slices & non-goals

- **Slice 1 (this build):** the home page, end-to-end (§§7–13).
- **Slice 2 (rest of M1):** methodology page (FR-007), explainer + "not financial advice" framing as a dedicated section (FR-006), CSV export (FR-008 — link the scorer's precomputed `exports/scores.csv`, synced like the JSON).
- **Later:** cash-rate overlay (FR-004, M2); shareable zoom/filter (FR-010, M3); auto tone summary (FR-012, M3).

**Non-goals reaffirmed for the front end** (from HANDOFF / [PRD §4](../../prd/rba-policy-sentiment/PRD.md)): never render full statement text (short evidence quotes only); no attribution of tone to individual board members; no forecasting, no advice/trading signals; decision media releases only; RBA only; no market/news/social sentiment; no accounts/personalisation. Disclaimers stay visible.

---

## 15. Risks & open items

| # | Risk / item | Mitigation |
| - | ----------- | ---------- |
| R-1 | `scores.json` payload size on first load (full breakdown for 64 decisions) | Monitor p95; if needed, split a slim `index` payload (net + outcome per decision) from per-decision detail fetched on demand. Not done in slice 1 (YAGNI). |
| R-2 | Stance/confidence bucket thresholds are a judgement call | Single source in `core.js`; documented on the methodology page; tunable without structural change. |
| R-3 | `file://` can't `fetch` local JSON | Documented local static-server step; production is served over HTTPS by Vercel. |
| R-4 | Data drift between repo `data/` and `apps/web/data/` | Generated + gitignored copy via `sync-data.mjs`; the repo root stays canonical. |
| R-5 | Engine changes later (transformer added, re-score) | Site is data-agnostic + N-component; only `sync-data.mjs` re-runs. |

---

## 16. Traceability

| Requirement | Where addressed |
| ----------- | --------------- |
| FR-003 stance chart | §8 |
| FR-005 statement detail | §7 (hero), §9 (panel) |
| FR-006 explainer | §14 slice 2 |
| FR-007 methodology | §14 slice 2 |
| FR-008 CSV | §14 slice 2 |
| FR-011 full granular breakdown | §9 |
| NFR-001 performance | §11 |
| NFR-003 transparency | §9, methodology (slice 2) |
| NFR-005 accessibility | §10, §11 |
| NFR-006 provenance | §9 (source links) |
| NFR-009 free-tier | §13 |
| NFR-010 privacy analytics | §11 |
| NFR-011 licensing | §9 (short quotes only) |
