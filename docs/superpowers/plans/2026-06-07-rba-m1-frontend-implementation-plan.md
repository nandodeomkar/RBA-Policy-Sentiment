# RBA Policy Sentiment — Milestone 1 Frontend Implementation Plan

| Field | Value |
| ----- | ----- |
| Status | Ready to execute |
| Date | 2026-06-07 |
| Design | [2026-06-07-rba-m1-frontend-design.md](../specs/2026-06-07-rba-m1-frontend-design.md) |
| Scope | **M1 slice 1 — the home page.** Slice 2 (methodology / explainer / CSV) is stubbed at the end. |

Dependency-ordered. Each step lists its **done** condition. 🧑 marks a **human-in-the-loop checkpoint** (something only you can do). The frontend is static + reads precomputed data, so there is **no API key or model** in the loop — I can build and test all of slice 1 autonomously; you're only needed to deploy.

> **Branching:** all M1 work (docs + code) is on **`feat/m1-frontend`**, branched off `feat/m0-scorer` so it carries the M0 data contract. It rebases/merges onto `main` after M0 lands. The spec and this plan are already committed here.

---

## Phase A — Scaffold `apps/web` + data sync

1. **App skeleton** — create `apps/web/` per design §3: `index.html` (empty shell), `styles.css` (the tracker's `:root`/dark tokens verbatim to start), `vendor/echarts.min.js` (vendor a **pinned** ECharts, copied from the tracker), `favicon.svg` + `robots.txt`, and `.gitignore` ignoring `apps/web/data/`.
   - *Done:* `apps/web/` matches design §3; `index.html` opens in a browser (blank but valid).
2. **Data sync script** — `apps/web/scripts/sync-data.mjs` copies repo-root `data/decisions.json` + `data/scores.json` → `apps/web/data/`. Pure Node, no deps.
   - *Done:* `node scripts/sync-data.mjs` populates `apps/web/data/`; re-runnable; the folder is gitignored (never committed).
3. **Deploy config + runbook** — `vercel.json` (root `apps/web`, build command `node scripts/sync-data.mjs`, static output) and `apps/web/README.md` (sync → local static server → deploy → the QA checklist).
   - *Done:* README's local-preview steps work end to end (`python -m http.server` serves the page over `http://`).

## Phase B — `core.js` engine (pure logic, unit-tested)

4. **Port reusable helpers** from the tracker's `core.js` — dates/numbers/`escapeHtml`/`countUp`/`initTheme`/`setupFilters`/`revealOnLoad`, plus `describeOutcome` (cut ▼ / hold ● / hike ▲). Dual export: `window.RBACore` **and** `module.exports`.
   - *Done:* helpers importable in Node and attached to `window`.
5. **Stance logic (new, pure)** — `stanceBucket(net)`, `confidenceBucket(conf)`, `signed(x,dp)`, `joinDecisions(decisions,scores)` per design §5–§6 (exact thresholds; half-open boundaries).
   - *Done:* implemented against the §6 tables.
6. **Unit tests** — `apps/web/tests/core.test.mjs` (`node --test`, zero deps): bucket boundaries (incl. the `−0.15/+0.15/±0.60` and `0.50/0.80` edges), `joinDecisions` ordering + skip-missing, `signed` minus glyph, `describeOutcome`.
   - *Done:* `node --test` is green.

## Phase C — Home page render (data → DOM)

7. **`index.html` structure** — topbar (wordmark + theme toggle), hero, "the record" section (filters + chart container), detail-panel container, full-record table, 3-block footer with **both disclaimers**, `<noscript>` fallback, and the Vercel analytics snippet. Semantic landmarks, single `<h1>`, skip link.
   - *Done:* structure validates; landmarks + skip link present; disclaimers visible.
8. **`app.js` bootstrap** — `fetch` both JSON files, `joinDecisions`, render loading skeleton → content; on failure show the fetch-fail message linking to the RBA decisions page.
   - *Done:* data renders on success; killing the data files shows the graceful fallback.
9. **Hero (latest decision)** — headline template (§7, no Governor-name assumption), net-stance track, three sub-score bars, confidence chip, one evidence quote, "Read the RBA statement →"; `countUp` on the net value.
   - *Done:* the `2026-05-05` example reads correctly (hawkish +0.31, hike → 4.35%, conf 0.69).
10. **`styles.css` sentiment components** — stance track, sub-score bars, confidence chip, detail panel, component cards, evidence chips; light **and** dark.
    - *Done:* both themes legible at AA contrast; nothing encoded by colour alone.

## Phase D — Chart, table, detail, filters

11. **Stance chart** (`buildStanceChart`, FR-003) — ECharts SVG line of net over time; fixed y `[−1,+1]` with emphasised `0` centreline, ends labelled Dovish/Hawkish; outcome-shaped markers; tooltip (§8); click a marker → open detail + set `#<id>`; leave the M2 second-axis seam; ECharts-fail fallback text.
    - *Done:* all 64 points render; click sets the hash + opens detail; `prefers-reduced-motion` honored; p95 load ≤ 2.5s (FR-003 acceptance).
12. **Full-record table** (`renderRecordTable`, NFR-005) — columns per §10, newest first, rows clickable **and** keyboard-operable → detail, horizontal scroll on mobile, empty-filter state.
    - *Done:* table is the chart's truth view; Enter/Space on a row opens its detail.
13. **Detail panel** (`renderDetail`, FR-005 + FR-011) — header + reconciled result + **N-component cards** (lexicon `matched_terms`; llm `rationale` + evidence) + reconciliation + evidence chips (polarity/dimension/source) + provenance footnote; **short quotes only**; open from hash on load.
    - *Done:* renders fully for a lexicon+llm decision; a synthetic 3rd component renders without code change; deep-link `#2026-05-05` opens it on load.
14. **Wire filters** (`setupFilters`) — Year select + outcome toggles + Reset + live status; drive chart **and** table together.
    - *Done:* filtering updates both views; the live status counts correctly; empty result shows the message.

## Phase E — Accessibility, QA, deploy, close

15. **Accessibility pass** (NFR-005) — focus states, heading order, shape+text (never colour-only), reduced-motion, ~360px touch targets, chart-has-table-equivalent.
    - *Done:* full keyboard pass; manual + axe checks clean.
16. **Manual QA** — run the README checklist: light/dark, ~375px mobile, keyboard, no-JS, fetch-fail, deep-link.
    - *Done:* checklist passes locally.
17. **Deploy** 🧑 — I finalize `vercel.json` + the build; **you connect/confirm the Vercel project** (or follow the README steps).
    - *Done:* a static deploy serves the home page; the build runs the sync; free-tier (NFR-009).
18. **Finalize** — mark FR-003 / FR-005 / FR-011 (home slice) progress in [TASKS.md](../../prd/rba-policy-sentiment/TASKS.md); add `apps/web` preview/sync commands to CLAUDE.md; open a PR for `feat/m1-frontend`.
    - *Done:* slice-1 acceptance criteria pass (chart renders chronologically ≤2.5s; the granular breakdown is visible per decision); PR opened.

---

## Slice 2 (later, still M1 — not built in this pass)

- **Methodology page** (`methodology.html`, FR-007) — corpus, each component, reconciliation, the score scales + bucket thresholds, limitations.
- **Explainer** (FR-006) — dovish vs hawkish + how to read the chart + the "not financial advice" framing as a first-class section.
- **CSV export** (FR-008) — link the scorer's precomputed `data/exports/scores.csv`, synced like the JSON.

## Human-in-the-loop summary (what I'll need from you)

| When | What |
| ---- | ---- |
| Step 17 | Connect / confirm the Vercel project for deploy (free tier) |
| Step 18 | Joint review before calling slice 1 done |
| (optional) | A visual spot-check at any point — say the word |

Everything else — scaffolding, the engine, rendering, the chart/table/detail, tests — I build and verify locally against the synced data, no credentials or models required.
