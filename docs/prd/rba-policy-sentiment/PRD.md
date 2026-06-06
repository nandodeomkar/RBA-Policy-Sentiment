---
title: "RBA Policy Sentiment"
status: final # draft | problem-review | solution-review | final | in-build | launched
version: 1.0.1
last_updated: "2026-06-06"
owner: "Omkar"
reviewers: [] # e.g. [eng-lead, design-lead, data]
preset: full # full | brief
overall_confidence: high # low | med | high
links:
  designs: "https://rba-tracker.vercel.app/"
  tickets: ""
  research: "See §13 References"
---

# RBA Policy Sentiment — Product Requirements Document

| Field      | Value |
| ---------- | ----- |
| Status     | Final |
| Version    | 1.0.1 |
| Owner      | Omkar |
| Reviewers  | Self (solo build via an AI coding agent) |
| Updated    | 2026-06-06 |
| Designs    | https://rba-tracker.vercel.app/ (design reference) |
| Tickets    | See TASKS.md (handoff) |
| Research   | See §13 References |

---

## 1. Overview / TL;DR

RBA Policy Sentiment is a public website that scores and visualises the **hawkish-to-dovish tone of the Reserve Bank of Australia's monetary policy decision statements over time**. After each rate decision the RBA publishes a short statement; on their own these are hard to compare across years and easy to over-read. A backend **reconciled hybrid ensemble** (LLM + transformer + finance lexicon) scores each statement into a **net dovish↔hawkish reading plus inflation, growth, and employment sub-tones**, every score backed by a full, inspectable breakdown and the evidence phrases behind it. The site plots the stance series over time alongside the cash rate, anchored by a "latest decision" hero and a full-record table. It serves **researchers** (a transparent, reproducible, citable dataset) and the **general public** (a plain-language read on which way the RBA is leaning) equally, through a layered UI. The north star is best-in-class accuracy and total methodological transparency — not traffic. [CONFIRMED]

---

## 2. Problem & Context

**Problem statement.** The RBA communicates its monetary policy stance largely through text — the post-meeting decision statement. Readers who want to understand how the Bank's tone has *shifted* (is it more hawkish than three meetings ago? more dovish than this time last year?) have no easy way to do it. Today they must read each statement and hold the comparison in their head. Stance is qualitative, scattered across many separate media releases, and not quantified anywhere official. [CONFIRMED]

**Evidence.** Grounded in the owner's own multi-year experience: *"I started off a few years ago reading the statements with no clue what to do with the info. Over the years I've developed an idea about past sentiment now that the rates have played out in the market, so whenever a new statement drops I compare them in my head from my own understanding."* That manual, in-the-head comparison is exactly what the product would externalise and make shareable. How readers cope today: reading each statement manually, leaning on bank/economist commentary, and media "hawkish/dovish" takes — all subjective, inconsistent, and not reproducible. Broad demand beyond the owner is still a hypothesis to test. [CONFIRMED: personal evidence + current workarounds] · [ASSUMPTION: wider demand — see Q-010]

**Why it matters.** The pain is real but moderate — a genuinely useful tool rather than a burning, must-solve need (owner-rated "useful," not critical). For researchers, a transparent, quantified stance series is a reusable, citable input for studying central-bank communication, forward guidance, and market reaction. For the general public, a simple visual answers "what did the RBA actually signal?" without needing to parse central-bank language. [CONFIRMED: severity is moderate]

**Why now.** No hard external trigger — the value is evergreen and the timing is flexible. The recent corpus is, however, structurally consistent (a dedicated Monetary Policy Board and a regular eight-meetings-a-year cadence following the 2025 RBA Review), which makes backfilling and ongoing ingestion cleaner. [CONFIRMED: no hard timing; evergreen]

---

## 3. Goals & Success Metrics

**Objectives**
- **Quality (north star):** produce best-in-class — "second to none" — stance scoring of RBA statements, using the strongest available methods (or a hybrid/ensemble), with a full, granular, per-score methodology that a reader can inspect for every score. [CONFIRMED]
- **User (researcher):** a credible, reproducible, citable stance dataset where each score's derivation is fully transparent.
- **User (general public):** let a non-expert grasp the RBA's current and historical leaning in under a minute, without sacrificing rigor.
- **Explicit non-objective:** traffic/visitor volume is *not* a success measure — accuracy and credibility are. [CONFIRMED]

**Success metrics**

| Type      | Metric                                              | Target & timeframe                              | Baseline |
| --------- | --------------------------------------------------- | ----------------------------------------------- | -------- |
| Primary   | Stance-score agreement with an expert/human-labelled benchmark | ≥ 85% agreement (or ≥ 0.8 rank correlation) on a held-out labelled set at launch; maintained or improved release-over-release [ASSUMPTION: exact threshold — accepted target, validate in M0] | None (pre-launch) |
| Input     | Per-score methodology coverage — every published score ships with a granular, inspectable breakdown (rationale + evidence phrases) | 100% of published scores [CONFIRMED] | 0 |
| Input     | Reproducibility — a third party can replicate any score from the published method + pinned engine version | Achieved at launch [CONFIRMED] | n/a |
| Guardrail | No misleading/incorrect scores reach users         | 0 materially-wrong published scores; any correction logged and dated [CONFIRMED] | n/a |
| Guardrail | p95 initial page load                              | ≤ 2.5s on a median connection [ASSUMPTION]      | n/a |

*Note: site traffic is observed via privacy-friendly analytics for interest only — it is not a success bar.* [CONFIRMED: analytics enabled, privacy-friendly]

---

## 4. Non-Goals / Out of Scope

- **Not other RBA document types in MVP** — only post-meeting monetary policy *decision statements*. Minutes, the Statement on Monetary Policy, and speeches are deferred (candidate fast-follows). [CONFIRMED: sources = decisions only]
- **Not other central banks** (Fed, ECB, RBNZ) — RBA only for now.
- **Not market or news sentiment** — we score the RBA's own words, not traders, media, or social.
- **Not a forecast** — the site does not predict the next rate decision or future stance.
- **Not financial advice / trading signals** — explicitly framed as informational and educational.
- **No user accounts, alerts, or personalisation in MVP** — anonymous, read-only site.
- **Not attributing sentiment to individual board members** — mirroring the RBA's own *unattributed* vote counts, scores describe the *statement*, never who on the board leaned which way. *(Note: multi-dimensional sentiment — inflation/growth/employment sub-tones — was previously excluded but is now **in scope**; see §7, resolves Q-009.)*
- **Not republishing full RBA statement text** — we link to the RBA source and quote only short evidence phrases (licensing-safe; resolves Q-005).

---

## 5. Target Users & Jobs-to-be-Done

**Primary personas (co-primary — both served deliberately)** [CONFIRMED: "both equally"]

- **Researcher / serious analyst** — spans academic economists, markets/finance professionals, and *self-taught RBA watchers* (the owner's own archetype: years of reading statements and building an intuition for tone). Needs a defensible, reproducible stance series with documented, per-score methodology and machine-readable export. [CONFIRMED]
- **Engaged member of the public** — e.g., curious mortgage-holders following rate decisions via news or personal interest. Needs a plain-language, at-a-glance read with no jargon. [CONFIRMED]

**Secondary / affected** [CONFIRMED]
- **Journalists** — may cite the chart or dataset around decision day.
- **Students** — learning how central-bank communication works.
- **Policy commentators** — referencing the stance series in analysis.

**Design note (consequence of "both equally").** Two very different audiences are co-primary, so the UX must be *layered*: a simple, plain-language surface a mortgage-holder grasps in under a minute, with progressive depth (per-score methodology, evidence phrases, raw data) one click away for researchers. Neither audience is sacrificed for the other. [CONFIRMED]

**Jobs-to-be-Done**
- When a new RBA decision lands, I want to see how its tone compares to recent meetings *without holding it all in my head*, so I instantly understand what changed.
- When I'm writing an analysis or paper, I want a reproducible stance score per meeting with its full methodology and source, so I can cite or build on it.
- When I'm a non-expert reading the news, I want a simple "leaning" indicator with a plain-language explanation, so I can follow what the RBA is signalling.

---

## 6. User Stories & Use Cases

### US-1 — See RBA stance over time  ·  Priority: P0
> As any visitor, I want to see a chart of the RBA's hawkish↔dovish stance across past decisions so that I can understand how its signalled position has shifted.

**Acceptance criteria**
- Given the site has scored statements, When I open the home page, Then a time-series chart of stance score renders with the most recent decision at the right edge, within 2.5s (p95).
- Given I hover or tap a point, When the tooltip appears, Then it shows the decision date, the stance score, and the rate action (hold/hike/cut).
- Given there is no data yet for a period, When the chart renders, Then gaps are shown honestly rather than interpolated.

### US-2 — Read a single decision in context  ·  Priority: P1
> As a visitor, I want to click a point and see that statement's score and a link to the RBA source so that I can verify and read more.

**Acceptance criteria**
- Given I select a data point, When the detail view opens, Then it shows the date, stance score, decision outcome, a short context line, and a link to the original RBA media release.
- Given I follow the source link, When it opens, Then it points to the canonical rba.gov.au release for that decision.

### US-3 — Understand the methodology  ·  Priority: P1
> As a researcher, I want a documented methodology and a downloadable dataset so that I can trust, reproduce, and cite the scores.

**Acceptance criteria**
- Given I open the methodology page, When I read it, Then it states the corpus, the scoring engine and version, the score scale, and known limitations.
- Given I download the dataset, When I open the CSV, Then each row has date, decision outcome, stance score, engine version, and source URL.

### US-4 — Understand the chart as a non-expert  ·  Priority: P1
> As a member of the public, I want a plain-language explainer of "hawkish vs dovish" and how to read the chart so that I can interpret it without a finance background.

**Acceptance criteria**
- Given I'm a first-time visitor, When the page loads, Then a one-line plain-language explanation of the axis (dovish ↔ hawkish) is visible without scrolling into jargon.
- Given I open the explainer, When I read it, Then it defines the terms in everyday language and includes a clear "not financial advice" note.

### US-5 — Inspect how a score was built  ·  Priority: P0
> As a researcher (or curious reader), I want to see exactly how each score was derived — sub-scores, the ensemble's per-component results, and the evidence phrases — so that the score is fully transparent, not a black box.

**Acceptance criteria**
- Given a statement detail view, When I open it, Then I see the net stance plus the inflation / growth / employment sub-scores.
- Given the breakdown, When I expand it, Then I see each component's result (LLM / transformer / lexicon) and the reconciled outcome, with a confidence indicator that reflects inter-model disagreement.
- Given the statement text, When rendered, Then hawkish- and dovish-leaning evidence phrases are visually distinguished.

---

## 7. Solution Overview & UX

**Approach.** A backend pipeline ingests each RBA monetary policy *decision media release* (post-2020 backfill plus each new release) and scores it with a **reconciled hybrid ensemble**: an LLM sentence-level classifier, a fine-tuned transformer (FinBERT-style), and a transparent finance/hawkish-dovish lexicon each score the text independently, and their outputs are reconciled into a final result, with inter-model disagreement surfaced as a confidence signal. Each statement yields a **net dovish↔hawkish score plus sub-dimension scores for inflation, growth, and employment tone**, and a **full granular breakdown** — per-component scores, the reconciliation, and the specific evidence phrases that drove each score. Everything is stored with the pinned engine version so any score is reproducible. The front end is static-first (serves precomputed JSON/CSV); the heavy lifting is the backend scoring job. [CONFIRMED: hybrid ensemble · decision release only · post-2020 · full granular · net + sub-dimensions]

**Why this engine.** RBA language is nuanced and formulaic. A reconciled ensemble gives best-in-class quality (no single method's blind spots dominate), the lexicon component keeps a transparent, reproducible baseline, and surfacing inter-model disagreement as confidence directly serves the "no misleading scores" guardrail. [CONFIRMED — resolves Q-001]

**Corpus & history.** Score the decision media release only (not the press conference or SoMP) — the cleanest, most consistent per-meeting unit. Backfill from 2020 onward. *Trade-off:* post-2020 is a small corpus (~40–50 decisions), which limits statistical signal and benchmark size (see R-002); the data model keeps history extensible so earlier decisions can be added later. [CONFIRMED — resolves Q-002, Q-003]

**Key flows.**
1. **Read the latest call** — land on home → a "Latest decision" hero shows the newest statement's net stance, sub-dimension tones, and rate outcome at a glance.
2. **Browse stance over time** — a line chart traces stance (and the cash rate) across decisions; hover / zoom / filter to explore.
3. **Inspect a decision** — select a point or table row → net + sub-scores, the reconciled per-component breakdown, highlighted evidence phrases, and a link to the RBA source.
4. **Go deeper** — open the methodology page and/or download the CSV.
5. **Stay current** — after a new decision, the maintainer runs the scoring job and the site reflects it (manual refresh).

**Designs / UX direction.** Inherit the design language of the owner's existing **RBA Board Vote Tracker** (rba-tracker.vercel.app) — same domain and audience: a warm off-white palette (theme `#f4f3ee`) with **light/dark mode**; an editorial, plain-language tone; a **"Latest decision" hero card**; a central **line chart** ("the path") with typed markers and Year/Type filters plus Reset; a **full-record table** that doubles as a screen-reader-friendly fallback for the chart; explainer sections; and a transparency-first footer with every figure **sourced to the RBA** and an "independent project — not an official RBA product" disclaimer. Our version swaps vote-splits for sentiment: the hero shows net + sub-dimension tone, the chart plots the stance series, and the table carries scores with per-row source links. [CONFIRMED: UI inspiration]

---

## 8. Functional Requirements

| ID     | Requirement (the need, not the solution) | Priority | Acceptance criteria | Traces to |
| ------ | ----------------------------------------- | -------- | ------------------- | --------- |
| FR-001 | The system shall ingest RBA monetary policy decision statements — a historical backfill and each newly published decision — capturing date, title, source URL, rate decision outcome, and the resulting cash-rate target. The statement text is fetched for scoring, but only short quoted evidence phrases are persisted/displayed (see §10 Licensing). | P0 | Given the RBA decision releases, When ingestion runs, Then each decision is stored once with all listed fields and a stable ID, with no full statement text persisted; re-running does not duplicate. | US-1, US-2 |
| FR-002 | The system shall score each statement with the reconciled hybrid ensemble, producing a net dovish↔hawkish score plus inflation, growth, and employment sub-scores on a fixed normalised scale, and store every component's result, the reconciled values, a confidence signal, and the pinned engine version. | P0 | Given an ingested statement, When scoring runs, Then net + three sub-scores (in range), all three component outputs, a confidence value, and the engine version are stored; re-scoring the same text + version is deterministic. | US-1, US-3, US-5 |
| FR-003 | The system shall present a time-series visualisation of stance score across all scored statements, in chronological order. | P0 | Given scored data, When the home page loads, Then the chart renders all points dated correctly and loads ≤ 2.5s (p95). | US-1 |
| FR-004 | The system shall let the user view the RBA cash-rate target on the same timeline for context (overlay or toggle). | P1 | Given the chart, When the user enables the rate series, Then cash-rate target steps render aligned to the same time axis. | US-1 |
| FR-005 | The system shall let the user select a data point and view that statement's score, decision outcome, a context line, and a link to the original RBA release. | P1 | Per US-2 acceptance criteria. | US-2 |
| FR-006 | The system shall provide a plain-language explainer of hawkish vs dovish and how to read the chart, including a "not financial advice" note. | P1 | Per US-4 acceptance criteria. | US-4 |
| FR-007 | The system shall publish a methodology page documenting the corpus, each ensemble component, the reconciliation logic, the net + sub-dimension score scales, and known limitations. | P0 | Per US-3 (methodology) acceptance criteria. | US-3, Goal: transparency |
| FR-008 | The system shall let users download the scored dataset as CSV (date, outcome, net score, inflation/growth/employment sub-scores, confidence, engine version, source URL). | P1 | Given the download action, When triggered, Then a well-formed CSV with those columns and one row per scored decision is returned. | US-3 |
| FR-009 | The system shall let the maintainer ingest + score a new decision via a manually-triggered batch job, after which the site reflects it. | P2 | Given a new RBA decision, When the maintainer runs the scoring job, Then the new statement is scored and appears on the chart and table. | US-1 |
| FR-010 | The system shall let users filter/zoom the time series by date range. | P2 | Given the chart, When the user sets a range, Then only that range renders and is shareable via URL. [ASSUMPTION] | US-1 |
| FR-011 | The system shall expose, for every score, the full granular breakdown — net + sub-scores, per-component (LLM / transformer / lexicon) results, the reconciliation, the confidence signal, and highlighted evidence phrases. | P0 | Per US-5 acceptance criteria. | US-5, Goal: transparency |
| FR-012 | The system shall show a short auto-generated plain-language summary of the latest decision's tone on the home page. | P2 | Given the latest scored decision, When the home page loads, Then a one–two sentence tone summary is shown with the score. [ASSUMPTION] | US-4 |

---

## 9. Non-Functional Requirements

| ID      | Category               | Requirement                                                                 | Priority |
| ------- | ---------------------- | --------------------------------------------------------------------------- | -------- |
| NFR-001 | Performance            | p95 initial load ≤ 2.5s; chart interaction (hover/zoom) ≤ 100ms. [ASSUMPTION] | P0 |
| NFR-002 | Reproducibility/Quality| Scores are computed once and persisted; re-running the pipeline on the same text + pinned engine version reproduces the stored score (LLM calls pinned/cached for determinism); engine version recorded per score. | P0 |
| NFR-003 | Transparency           | Methodology is publicly documented and sufficient for a third party to reproduce the approach, including the ensemble reconciliation and sub-dimension scoring. | P0 |
| NFR-004 | Accuracy               | Stance scores meet the §3 benchmark agreement target (≥ 85% vs expert labels) before public launch. [ASSUMPTION] | P0 |
| NFR-005 | Accessibility          | WCAG 2.1 AA; the chart has an accessible text/table equivalent. [ASSUMPTION] | P1 |
| NFR-006 | Data provenance        | Every score links to its canonical rba.gov.au source. | P0 |
| NFR-007 | Reliability            | Static-first delivery; ≥ 99% availability; degrades gracefully if the scoring job fails (last good data stays live). [ASSUMPTION] | P1 |
| NFR-008 | Scalability            | Absorb traffic spikes on decision days (8×/year, ~2:30 pm AEST) without degradation. [ASSUMPTION] | P1 |
| NFR-009 | Cost                   | Run within free-tier hosting limits (front end on Vercel; scoring as an offline batch job). [CONFIRMED] | P1 |
| NFR-010 | Privacy                | No accounts/PII; any analytics is privacy-respecting. [ASSUMPTION] | P2 |
| NFR-011 | Compliance/Licensing   | Link to RBA sources and store/show only short quotes (never full statements); attribute the source throughout. [CONFIRMED — Q-005] | P1 |

---

## 10. Technical Considerations, Dependencies & Constraints

**Constraints.** Web, responsive (desktop + mobile). **Stack: Next.js front end on Vercel** (mirroring the owner's existing tracker), with a **separate Python batch job** for scoring. Must run on **free-tier hosting**. Scoring is a batch job **triggered manually** after each decision — no always-on service required. [CONFIRMED — resolves Q-004]

**Dependencies.**
| Dependency | Type | Owner | Status |
| ---------- | ---- | ----- | ------ |
| RBA decision releases (rba.gov.au media releases / decisions index) | External | RBA | Available, public |
| RBA cash-rate target series (RBA statistics) | External | RBA | Available, public |
| Hybrid ensemble engine — LLM API + transformer + lexicon | External/Internal | Omkar | Selected (Q-001); to build |
| Validation benchmark — published/academic labels | External | Omkar | Source TBC — published labels for post-2020 RBA decisions may be scarce; fallback = self-label a small set (Q-006) |
| Hosting — Vercel, free tier | External | Vercel | Selected (Q-004) |
| LLM API provider for scoring | External | TBD | To select; must fit free/low-cost budget |

**APIs & integrations.** Data is acquired by fetching/parsing published RBA pages (no official decisions API). Scoring calls an external LLM API plus a local transformer + lexicon. Cash-rate data comes from RBA statistics. Per licensing (below), the app **links to RBA sources and stores only short quotes**, never full statement text. [CONFIRMED]

**Data & analytics.** Core entity `decision` (id, date, outcome, cash_rate_target, source_url, short_quote) with a one-to-one `score` carrying net + inflation/growth/employment sub-scores, per-component (LLM / transformer / lexicon) results, reconciliation, confidence, evidence-phrase spans, engine_version, scored_at. Privacy-friendly analytics capture chart interactions, CSV downloads, methodology-page views, and basic page-load timing (to monitor the p95 load guardrail in §3). [CONFIRMED: analytics]

**Licensing.** Link-and-short-quote approach: every decision links to its rba.gov.au source and only brief quoted phrases (the evidence spans) are stored/shown — never the full statement. Safest reading of RBA's terms and sufficient for the product. [CONFIRMED — resolves Q-005]

**Design doc.** [TBD] — engineering design (parser robustness, the ensemble + reconciliation logic, storage, Vercel deployment) to be written before build.

---

## 11. Release & Rollout Plan

**Milestones / phases**

| Phase | Scope (requirement IDs) | Target | Exit criteria |
| ----- | ----------------------- | ------ | ------------- |
| M0 — Data + engine | FR-001, FR-002 + benchmark (Q-006) | Week 1 | Post-2020 statements ingested; reconciled ensemble built; scores meet the §3 accuracy guardrail on the benchmark. |
| M1 — Public MVP | FR-003, FR-005, FR-006, FR-007, FR-008, FR-011 | Weeks 2–3 | Chart + full-record table live with backfilled data; statement detail with the full granular breakdown (per-component + evidence phrases); explainer; methodology page; CSV; NFR-001/002/003/004/006 met. |
| M2 — Context + currency | FR-004, FR-009 | Week 3 | Cash-rate overlay live; the manual refresh process is documented and working. |
| M3 — Depth (post-launch) | FR-010, FR-012 | Later | Date zoom/filter; latest-decision plain-language summary. |

**Rollout strategy.** Soft launch: build the MVP over ~a few weeks (via an AI coding agent), validate scoring accuracy and methodology with a few researchers, then promote — decision days are natural amplification windows. [CONFIRMED — resolves Q-007: ~few weeks; built via an AI coding agent; soft launch]

**Launch criteria.** Backfilled stance series + sub-scores render correctly; scores pass the accuracy guardrail; every score exposes its granular breakdown; methodology page is published; every score links to its RBA source; "not financial advice" and "independent — not an official RBA product" disclaimers are present. [CONFIRMED]

**GTM coordination.** Lightweight — share with academic / econ communities and around a decision day. [ASSUMPTION]

---

## 12. Risks, Assumptions & Open Questions

**Assumptions** (open items are tracked as risks below)
- [ASSUMPTION] The ≥ 85% benchmark-agreement target (§3) is the right bar for "world-class" — *validate by: researcher feedback + benchmark labelling in M0; accepted risk R-001/R-002.*
- [ASSUMPTION] RBA decision pages are reliably parseable and stable enough to backfill and monitor — *validate by: M0 ingestion spike; accepted risk R-003.*
- [ASSUMPTION] A usable published/academic label set exists for the benchmark; if not, the owner self-labels a small set — *validate by: M0 benchmark sourcing (Q-006).*
- [ASSUMPTION] Wider demand beyond the owner exists — held lightly; not a launch gate, since success is accuracy/transparency, not traffic — *validate by: post-launch interest signals.*

**Risks**
| ID    | Risk | Likelihood | Impact | Mitigation |
| ----- | ---- | ---------- | ------ | ---------- |
| R-001 | Scores are perceived as invalid/arbitrary, undermining credibility with researchers. | M | H | Publish methodology; validate against a human-labelled benchmark; pin engine version; show explainability (FR-011). |
| R-002 | Small corpus (~40–50 short statements post-2020) yields weak/noisy signal and a thin benchmark. | M | M | Sentence-level + sub-dimension scoring; keep the data model extensible to add pre-2020 decisions later; consider adding minutes/SoMP post-MVP. |
| R-003 | RBA changes statement format or board structure (already shifted to the Monetary Policy Board, 2025), breaking ingestion. | M | M | Resilient parser + monitoring/alerts on ingest; manual fallback. |
| R-004 | Licensing/copyright limits redistribution of RBA text. | L | M | Resolved: link to sources + short quotes only, never full text; attribute throughout (Q-005). |
| R-005 | Public reads scores as a buy/sell or rate-forecast signal. | M | M | Prominent "not financial advice"/"not a forecast" framing; plain-language explainer. |
| R-006 | LLM-based scoring drifts across model versions, hurting reproducibility. | M | M | Pin model/version per score; re-score under version bumps; expose version in data. |

**Open Questions**
| ID    | Question | Owner | Status | Resolution / Date |
| ----- | -------- | ----- | ------ | ----------------- |
| Q-001 | Confirm the scoring engine. | Omkar | Answered | Reconciled hybrid ensemble (LLM + transformer + lexicon). 2026-06-06 |
| Q-002 | Exactly which text per decision? | Omkar | Answered | Decision media release only. 2026-06-06 |
| Q-003 | How far back should the backfill go? | Omkar | Answered | From 2020 onward; history kept extensible. 2026-06-06 |
| Q-004 | Preferred stack, hosting, and budget? | Omkar | Answered | Next.js on Vercel (free tier) + Python batch scoring. 2026-06-06 |
| Q-005 | Licensing terms for RBA text? | Omkar | Answered | Link to source + short quotes only; no full-text redistribution. 2026-06-06 |
| Q-006 | Who creates the validation benchmark? | Omkar | Answered | Prefer published/academic labels; fallback = self-label a small set if none fit post-2020. 2026-06-06 |
| Q-007 | Who owns/maintains this, and target launch date? | Omkar | Answered | Owner Omkar; built via an AI coding agent; ~a few weeks to a soft launch. 2026-06-06 |
| Q-008 | Desired freshness after a new decision? | Omkar | Answered | Manual trigger is acceptable for MVP. 2026-06-06 |
| Q-009 | Single net stance score, or multi-dimensional tone? | Omkar | Answered | Net + inflation/growth/employment sub-dimensions, in scope for MVP. 2026-06-06 |
| Q-010 | Are there existing tools/datasets to position against? | Omkar | Deferred | Known alternatives today: manual reading, economist/media commentary; no known quantified RBA stance series. Full scan deferred — non-blocking. 2026-06-06 |

---

## 13. Appendix, References & Glossary

**References.**
- RBA Media Releases — https://www.rba.gov.au/media-releases/
- RBA Monetary Policy Decisions index — https://www.rba.gov.au/monetary-policy/int-rate-decisions/
- RBA Statement on Monetary Policy — https://www.rba.gov.au/publications/smp/
- RBA Cash Rate Target (history & data) — https://www.rba.gov.au/statistics/cash-rate/
- Design reference — owner's RBA Board Vote Tracker — https://rba-tracker.vercel.app/
- Methodology literature on central-bank hawkish/dovish text scoring — to be compiled for the methodology page (e.g., Loughran-McDonald finance sentiment; central-bank communication / hawkish-dovish dictionary research).

**Glossary.**
- **Hawkish** — leaning toward tighter policy (e.g., raising or holding rates higher to curb inflation).
- **Dovish** — leaning toward looser policy (e.g., cutting or holding rates lower to support growth/employment).
- **Stance score** — this site's normalised reading of how hawkish/dovish a statement is: a net score plus inflation, growth, and employment sub-scores.
- **Cash rate target** — the RBA's policy interest rate, set at each decision.
- **Monetary Policy Board** — the RBA board responsible for monetary policy decisions following the 2025 RBA Review (historically the Reserve Bank Board).
- **SoMP** — Statement on Monetary Policy, the RBA's quarterly economic assessment.
- **Reconciled hybrid ensemble** — combining an LLM classifier, a transformer model, and a lexicon, then reconciling their outputs into one score, with a confidence signal derived from how much they (dis)agree.
- **Sub-dimension score** — tone on a specific theme (inflation, growth, or employment) reported alongside the net hawkish/dovish stance.

### Change Log
| Version | Date       | Author | Change        |
| ------- | ---------- | ------ | ------------- |
| 0.1.0   | 2026-06-06 | Omkar  | Initial draft |
| 0.2.0   | 2026-06-06 | Omkar  | Clarified §§2–11; locked hybrid-ensemble engine, multi-dimensional scoring, post-2020 corpus, Vercel/free-tier stack, link-only licensing; resolved Q-001–006, Q-008, Q-009 |
| 1.0.0   | 2026-06-06 | Omkar  | Finalized; consistency pass (fixed metric/scope/licensing contradictions); approved to build |
| 1.0.1   | 2026-06-06 | Omkar  | Handoff generated (HANDOFF.md + TASKS.md) |
