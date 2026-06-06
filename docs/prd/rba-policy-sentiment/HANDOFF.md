# RBA Policy Sentiment — Implementation Handoff

> **Read me first.** This is the lean entry point for building RBA Policy Sentiment. It carries
> everything you need to start. For full detail on any item, open the linked section in `PRD.md`
> **only when you begin the task that needs it** — do not load the whole PRD up front.

**Source of truth:** `./PRD.md` (version 1.0.0, status: final) · **Tasks:** `./TASKS.md`

---

## What & why

A public website that scores and visualises the **hawkish↔dovish tone of the Reserve Bank of Australia's monetary policy decision statements over time**. Today the only way to compare the RBA's tone across meetings is to re-read each statement and hold the comparison in your head; this product externalises that into a reproducible, inspectable stance series. A **Python batch job** scores each decision media release with a **reconciled hybrid ensemble** (LLM + transformer + finance lexicon) into a **net dovish↔hawkish score plus inflation, growth, and employment sub-tones**, each with a full granular breakdown and the evidence phrases behind it. A **Next.js** site plots the series over time with a "latest decision" hero and a full-record table. It serves **researchers** (reproducible, citable data) and the **general public** (plain-language read) equally. (PRD §1–2.)

## Goals

- **North star:** best-in-class, fully transparent stance scoring — every score inspectable down to its per-component results and evidence phrases.
- A **reproducible, citable** dataset for researchers.
- A **plain-language, under-a-minute** read for the public, via a layered UI.
- Explicitly **not** a traffic goal — accuracy and credibility are what matter. (PRD §3.)

## Non-goals (do NOT build these)

- **No other RBA document types** — decision media releases only (no minutes, SoMP, speeches).
- **No other central banks** (Fed/ECB/RBNZ).
- **No market / news / social sentiment** — only the RBA's own words.
- **No forecasting** of future decisions or stance.
- **No financial advice / trading signals.**
- **No user accounts, alerts, or personalisation.**
- **No attributing sentiment to individual board members.**
- **Do not persist or republish full RBA statement text** — link + short evidence quotes only.

<!-- Non-goals are mandatory. Anything not stated as in-scope is out of scope; do not add it. -->

## Success metrics (build the instrumentation for these)

- **Primary:** ≥ 85% agreement (or ≥ 0.8 rank correlation) with an expert/human-labelled benchmark at launch. *(Accepted target — validate in M0; it gates public launch.)*
- **Guardrail:** zero materially-wrong published scores (log + date any correction).
- **Guardrail:** p95 page load ≤ 2.5s — emit page-load timing to measure it.
- **Coverage:** 100% of published scores ship a granular breakdown; every score reproducible from the pinned engine version. (PRD §3.)

## Tech stack & hard constraints

- **Front end:** Next.js on **Vercel**. Inherit the design language of `rba-tracker.vercel.app` — warm `#f4f3ee` palette, **light/dark mode**, editorial/plain-language tone, "Latest decision" hero, central line chart with Year/Type filters + Reset, **full-record table that doubles as the accessible (WCAG 2.1 AA) fallback**, transparency-first footer sourcing every figure to the RBA + "independent — not an official RBA product" disclaimer.
- **Scoring:** a **separate Python batch job** — reconciled hybrid ensemble (LLM API + transformer + finance/hawkish-dovish lexicon), **manually triggered**.
- **Must run within free-tier limits** (NFR-009); **static-first** delivery — the site serves precomputed JSON/CSV.
- **Reproducibility (NFR-002):** compute scores once and persist them; pin/cache LLM calls; record engine version per score.
- **Accuracy gate (NFR-004):** scores must pass the benchmark before public launch.
- **Provenance (NFR-006):** every score links to its canonical `rba.gov.au` source.
- **Licensing (NFR-011):** link + short quotes only, never full statement text; attribute throughout.
- **Design doc for the "how":** [TBD] — write before build (parser robustness, ensemble + reconciliation logic, storage, deployment).

## Milestone roadmap

| Phase | Goal | Key requirement IDs |
| ----- | ---- | ------------------- |
| M0 — Data + engine | Ingest post-2020 decisions; build the scorer; pass the accuracy benchmark | FR-001, FR-002, NFR-002, NFR-004, NFR-006 |
| M1 — Public MVP | Chart + table, statement detail w/ full breakdown, explainer, methodology, CSV | FR-003, FR-005, FR-006, FR-007, FR-008, FR-011 |
| M2 — Context + currency | Cash-rate overlay; documented manual refresh | FR-004, FR-009, NFR-007 |
| M3 — Depth (post-launch) | Date zoom/filter; latest-decision tone summary | FR-010, FR-012 |

## How to work here

- Read this brief first; open the relevant `PRD.md` section **only when you start that task**.
- Each requirement's **acceptance criteria are its Definition of Done** — find them by ID in the PRD.
- **Respect the non-goals.** Do not add unrequested features or infer scope from omission.
- Work milestone by milestone. Expand each high-level task in `TASKS.md` into concrete sub-tasks **when you pick it up**, not before.
- **M0 is a hard gate:** do not ship publicly until scores pass the accuracy benchmark (NFR-004).
- When a requirement is ambiguous, check the PRD section; if still unclear, ask the owner rather than assume.

## PRD index (jump to detail on demand)

| #  | Section                                  | Anchor / link             |
| -- | ---------------------------------------- | ------------------------- |
| 1  | Overview / TL;DR                         | `PRD.md#1-overview--tldr` |
| 2  | Problem & Context                        | `PRD.md#2-problem--context` |
| 3  | Goals & Success Metrics                  | `PRD.md#3-goals--success-metrics` |
| 4  | Non-Goals / Out of Scope                 | `PRD.md#4-non-goals--out-of-scope` |
| 5  | Target Users & JTBD                      | `PRD.md#5-target-users--jobs-to-be-done` |
| 6  | User Stories & Use Cases                 | `PRD.md#6-user-stories--use-cases` |
| 7  | Solution Overview & UX                   | `PRD.md#7-solution-overview--ux` |
| 8  | Functional Requirements                  | `PRD.md#8-functional-requirements` |
| 9  | Non-Functional Requirements              | `PRD.md#9-non-functional-requirements` |
| 10 | Technical Considerations & Dependencies  | `PRD.md#10-technical-considerations-dependencies--constraints` |
| 11 | Release & Rollout Plan                   | `PRD.md#11-release--rollout-plan` |
| 12 | Risks, Assumptions & Open Questions      | `PRD.md#12-risks-assumptions--open-questions` |
| 13 | Appendix, References & Glossary          | `PRD.md#13-appendix-references--glossary` |
