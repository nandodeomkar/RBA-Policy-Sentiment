# RBA Policy Sentiment — Task Plan

Phased, dependency-ordered tasks derived from `PRD.md`. Tasks are intentionally **high-level**.
When you start a task, expand it into concrete sub-tasks — do not pre-expand everything.

**How to use:** Work top to bottom. Each task links to the PRD requirement IDs it implements;
those requirements' acceptance criteria are the Definition of Done. Check the box when the
acceptance criteria pass.

> Keep phases agent-sized (~30–50 requirements each). This project is small (12 FRs + 11 NFRs),
> so each phase is well within budget.

---

## Milestone 0 — Data + engine (foundation, hard gate)
*Exit criteria (PRD §11): post-2020 statements ingested; reconciled ensemble built; scores meet the §3 accuracy guardrail on the benchmark.*

> **Status — 2026-06-07:** Phases A–D shipped. Ingestion, cash-rate data, benchmark harness/rubric, and the **reconciled hybrid ensemble (FR-002)** are built; the **full lexicon + LLM + transformer** ensemble is now **live over all 64 decisions** — full FR-011 breakdown, byte-identical re-runs (NFR-002), licensing-clean, reproducible (engine `engine-2026.06-57c7cd6e`). The transformer runs via a pluggable model slot ([design](../../superpowers/specs/2026-06-07-rba-pluggable-transformer-models-design.md)) with the non-gated interim **fed-stance** model — FOMC-RoBERTa is gated; it and an RBA-specific model are swap targets once access lands. Remaining for the M0 gate: **owner labels → accuracy-gate validation** (Phase E). Legend: `[x]` done · ◐ partial · `[ ]` not started.

- [x] **Build the decision-ingestion pipeline** — implements FR-001 · DoD: PRD §8 — ✅ *Phase B: 64 post-2020 decisions, stable IDs, no full text, idempotent re-runs; parser tests green.*
  - <!-- expand at implementation time: fetch/parse RBA decision releases from 2020+, capture date/title/source URL/outcome/cash-rate target, persist only short evidence quotes (never full text), idempotent re-runs -->
- [x] **Ingest the RBA cash-rate target series** — supports FR-004 · DoD: PRD §10 (data dependency) — ✅ *Phase B: cash-rate table parsed and joined to each decision (target + hold/hike/cut outcome).*
- [x] **Build the reconciled hybrid ensemble scorer** — implements FR-002, NFR-002 · DoD: PRD §8, §9 — ✅ *Full ensemble (lexicon + LLM + transformer) live over all 64 — per-component results, reconciliation, confidence, evidence, FR-011 breakdown; byte-identical re-runs (NFR-002); engine `engine-2026.06-57c7cd6e`. Transformer wired via a pluggable model slot ([design](../../superpowers/specs/2026-06-07-rba-pluggable-transformer-models-design.md)) running the non-gated interim **fed-stance** model. Fed→RBA transfer quality + accuracy validation are tracked under NFR-004 (deferred — owner labels).*
  - <!-- LLM + transformer + lexicon each score independently; reconcile to net + inflation/growth/employment sub-scores; emit per-component results, confidence (from disagreement), evidence-phrase spans, pinned engine version; compute-once-and-persist, pin/cache LLM calls -->
- [ ] **Source or build the validation benchmark** — supports NFR-004 (Q-006) · DoD: PRD §9 — ◐ *Partial (Phase C): `RUBRIC.md` + 64-row `labels.csv` template + tested split/metrics/gate harness built. Remaining: owner fills the labels; quick published-label scan.*
  - <!-- prefer published/academic labels; fallback = self-label a small held-out set -->
- [ ] **Validate accuracy against the benchmark** — implements NFR-004 · DoD: PRD §9 — *Blocked on owner labels (Phase E) — full-ensemble scores now exist. Also quantifies the interim Fed model's transfer to RBA text (whether to keep, down-weight, or swap it). The hard gate: no public launch until within-one-bucket ≥85% passes.*
  - <!-- must reach ≥85% agreement / ≥0.8 rank correlation before any public launch -->
- [x] **Wire score provenance** — implements NFR-006 · DoD: PRD §9 (every score links to its rba.gov.au source) — ✅ *Every one of the 64 scores carries its canonical `rba.gov.au` `source_url` (verified: 0 without provenance).*

## Milestone 1 — Public MVP
*Exit criteria (PRD §11): chart + full-record table live with backfilled data; statement detail with the full granular breakdown; explainer; methodology page; CSV; NFR-001/002/003/004/006 met.*

> **Status — 2026-06-07:** **Slices 1 & 2 built** on `feat/m1-frontend` (vanilla static, mirrors RBA-Tracker). Slice 1: "Latest decision" hero, stance-over-time chart, full-record table, full granular breakdown panel. **Slice 2: plain-language explainer + above-the-fold axis line (FR-006), methodology page (FR-007), CSV export (FR-008).** Light/dark; data sync; unit tests (11 green). Verified in preview (light/dark, mobile, keyboard, fetch-fail, deep-link, CSV serves, methodology facts fill from live data). **Remaining for M1:** confirm analytics/page-load timing on deploy; finalize NFR sign-off. **Public launch still gated on the M0 accuracy gate (NFR-004).**

- [x] **Stance-over-time chart** — implements FR-003 · DoD: PRD §8 — ✅ *Slice 1: ECharts net-stance line + outcome-shaped markers; all 64 render chronologically (p95 ≤2.5s to confirm on deploy).*
- [x] **Statement detail with full granular breakdown** — implements FR-005, FR-011 · DoD: PRD §8 — ✅ *Slice 1: per-decision panel — per-component results, reconciliation, confidence, evidence phrases, source link; deep-linkable via `#id`.*
  - <!-- net + sub-scores, per-component (LLM/transformer/lexicon) results, reconciliation, confidence, highlighted evidence phrases, source link -->
- [x] **Plain-language explainer + "not financial advice" note** — implements FR-006 · DoD: PRD §8 — ✅ *Slice 2: above-the-fold axis one-liner in the hero + a dedicated "Hawkish, dovish — in plain language" section (terms in everyday language, how to read the chart, sub-scores/confidence) with a clear "not financial advice / not affiliated with the RBA" note. (US-4 criteria met.)*
- [x] **Methodology page** — implements FR-007 · DoD: PRD §8 (corpus, each component, reconciliation, score scales, limitations) — ✅ *Slice 2: `methodology.html` — corpus, the lexicon+LLM+transformer ensemble (incl. the interim **fed-stance** caveat), reconciliation + confidence, score scales + bucket thresholds, reproducibility/provenance with a live engine fingerprint, and known limitations (incl. **accuracy gate not yet validated**). Volatile facts fill from the live data.*
- [x] **CSV export** — implements FR-008 · DoD: PRD §8 (date, outcome, net + sub-scores, confidence, engine version, source URL) — ✅ *Slice 2: `data/scores.csv` precomputed at sync time (`buildScoresCsv` in core.js, unit-tested), served as a static file; "Download CSV" on the home page + methodology. One row per decision; verified well-formed (64 rows + header).*
- [x] **Design language + light/dark + accessible table fallback** — implements NFR-005 · DoD: PRD §7, §9 — ✅ *Slice 1: inherits RBA-Tracker tokens; light/dark; full-record table is the chart's accessible equivalent.*
- [ ] **Instrumentation** — emit privacy-friendly analytics + page-load timing for the §3 metrics/guardrails (PRD §3, §10) — ◐ *Vercel cookieless analytics snippet wired; `csv_download` + `methodology_view` custom events added (slice 2); confirm events + page-load timing on deploy.*
- [ ] **Meet performance / cost / licensing / privacy NFRs** — NFR-001, NFR-009, NFR-010, NFR-011 · DoD: PRD §9

## Milestone 2 — Context + currency
*Exit criteria (PRD §11): cash-rate overlay live; the manual refresh process is documented and working.*

- [ ] **Cash-rate overlay on the timeline** — implements FR-004 · DoD: PRD §8
- [ ] **Manual refresh workflow** — implements FR-009 · DoD: PRD §8 (maintainer-triggered ingest + score of a new decision; document the runbook)
- [ ] **Reliability & decision-day resilience** — NFR-007, NFR-008 · DoD: PRD §9 (static-first; last good data stays live if the job fails)

## Milestone 3 — Depth (post-launch)
*Exit criteria (PRD §11): date zoom/filter; latest-decision plain-language summary.*

- [ ] **Date zoom / filter** — implements FR-010 · DoD: PRD §8 (range render; shareable via URL)
- [ ] **Latest-decision plain-language tone summary** — implements FR-012 · DoD: PRD §8

---

## Cross-cutting (apply throughout)
- [ ] Meet non-functional requirements NFR-001 … NFR-011 (PRD §9)
- [ ] Honor all non-goals (PRD §4) — do not add unrequested scope (no forecasts, no advice, no other doc types/banks, no member attribution, no full-text storage)
- [ ] Keep disclaimers visible: "not financial advice" and "independent — not an official RBA product" (PRD §11 launch criteria)
- [ ] Tests cover the acceptance criteria for every P0/P1 requirement

## Traceability
| Requirement | Milestone | Task |
| ----------- | --------- | ---- |
| FR-001 | M0 | Decision-ingestion pipeline |
| FR-002 | M0 | Reconciled hybrid ensemble scorer |
| FR-003 | M1 | Stance-over-time chart |
| FR-004 | M2 | Cash-rate overlay |
| FR-005 | M1 | Statement detail |
| FR-006 | M1 | Plain-language explainer |
| FR-007 | M1 | Methodology page |
| FR-008 | M1 | CSV export |
| FR-009 | M2 | Manual refresh workflow |
| FR-010 | M3 | Date zoom / filter |
| FR-011 | M1 | Full granular breakdown (with FR-005) |
| FR-012 | M3 | Latest-decision tone summary |
| NFR-002 | M0 | Reconciled hybrid ensemble scorer |
| NFR-004 | M0 | Validate accuracy against benchmark |
| NFR-006 | M0 | Score provenance |
| NFR-001 | M1 | Performance (chart + instrumentation) |
| NFR-003 | M1 | Transparency (methodology page) |
| NFR-005 | M1 | Accessibility (table fallback) |
| NFR-009/010/011 | M1 | Cost / privacy / licensing |
| NFR-007/008 | M2 | Reliability & resilience |
