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

> **Status — 2026-06-06:** Phases A–D shipped. Ingestion, cash-rate data, benchmark harness/rubric, and the **reconciled ensemble scorer (FR-002)** are built; the **lexicon+LLM** configuration is **live over all 64 decisions** — full FR-011 breakdown, deterministic re-runs, licensing-clean, reproducible LLM cache. Remaining for the M0 gate: wire the **transformer** into the live ensemble (code done, run deferred) and **owner labels → accuracy-gate validation** (Phase E). Legend: `[x]` done · ◐ partial · `[ ]` not started.

- [x] **Build the decision-ingestion pipeline** — implements FR-001 · DoD: PRD §8 — ✅ *Phase B: 64 post-2020 decisions, stable IDs, no full text, idempotent re-runs; parser tests green.*
  - <!-- expand at implementation time: fetch/parse RBA decision releases from 2020+, capture date/title/source URL/outcome/cash-rate target, persist only short evidence quotes (never full text), idempotent re-runs -->
- [x] **Ingest the RBA cash-rate target series** — supports FR-004 · DoD: PRD §10 (data dependency) — ✅ *Phase B: cash-rate table parsed and joined to each decision (target + hold/hike/cut outcome).*
- [ ] **Build the reconciled hybrid ensemble scorer** — implements FR-002, NFR-002 · DoD: PRD §8, §9 — ◐ *Partial (Phase D): LLM + transformer + lexicon components, reconciliation, confidence, evidence merge, and composite `engine_version`/compute-once all built and tested. **Lexicon+LLM live over 64 decisions** — full FR-011 breakdown, byte-identical re-runs (NFR-002), committed reproducible LLM cache. Remaining: wire the transformer into the live ensemble (step 16, deferred).*
  - <!-- LLM + transformer + lexicon each score independently; reconcile to net + inflation/growth/employment sub-scores; emit per-component results, confidence (from disagreement), evidence-phrase spans, pinned engine version; compute-once-and-persist, pin/cache LLM calls -->
- [ ] **Source or build the validation benchmark** — supports NFR-004 (Q-006) · DoD: PRD §9 — ◐ *Partial (Phase C): `RUBRIC.md` + 64-row `labels.csv` template + tested split/metrics/gate harness built. Remaining: owner fills the labels; quick published-label scan.*
  - <!-- prefer published/academic labels; fallback = self-label a small held-out set -->
- [ ] **Validate accuracy against the benchmark** — implements NFR-004 · DoD: PRD §9 — *Blocked on FR-002 scores + owner labels (Phase E). The hard gate: no public launch until within-one-bucket ≥85% passes.*
  - <!-- must reach ≥85% agreement / ≥0.8 rank correlation before any public launch -->
- [x] **Wire score provenance** — implements NFR-006 · DoD: PRD §9 (every score links to its rba.gov.au source) — ✅ *Every one of the 64 scores carries its canonical `rba.gov.au` `source_url` (verified: 0 without provenance).*

## Milestone 1 — Public MVP
*Exit criteria (PRD §11): chart + full-record table live with backfilled data; statement detail with the full granular breakdown; explainer; methodology page; CSV; NFR-001/002/003/004/006 met.*

- [ ] **Stance-over-time chart** — implements FR-003 · DoD: PRD §8 (renders all points chronologically; loads ≤2.5s p95; honest gaps)
- [ ] **Statement detail with full granular breakdown** — implements FR-005, FR-011 · DoD: PRD §8
  - <!-- net + sub-scores, per-component (LLM/transformer/lexicon) results, reconciliation, confidence, highlighted evidence phrases, source link -->
- [ ] **Plain-language explainer + "not financial advice" note** — implements FR-006 · DoD: PRD §8
- [ ] **Methodology page** — implements FR-007 · DoD: PRD §8 (corpus, each component, reconciliation, score scales, limitations)
- [ ] **CSV export** — implements FR-008 · DoD: PRD §8 (date, outcome, net + sub-scores, confidence, engine version, source URL)
- [ ] **Design language + light/dark + accessible table fallback** — implements NFR-005 · DoD: PRD §7, §9 (inherit rba-tracker look; chart has WCAG 2.1 AA table equivalent)
- [ ] **Instrumentation** — emit privacy-friendly analytics + page-load timing for the §3 metrics/guardrails (PRD §3, §10)
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
