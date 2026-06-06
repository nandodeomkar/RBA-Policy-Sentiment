# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

**Pre-implementation.** This repo currently contains only the planning documents for *RBA Policy Sentiment* under [docs/prd/rba-policy-sentiment/](docs/prd/rba-policy-sentiment/). There is **no application code, no build tooling, and no git history yet** — so there are no build/lint/test commands to run. The stack is decided (see below) but nothing has been scaffolded. The first real implementation work is Milestone 0 in [TASKS.md](docs/prd/rba-policy-sentiment/TASKS.md).

When you scaffold the apps, add the concrete build/test/lint commands to this file.

## The planning docs (source of truth)

Read these in order; do **not** load the whole PRD up front.

1. [HANDOFF.md](docs/prd/rba-policy-sentiment/HANDOFF.md) — the lean entry point. Read this first.
2. [TASKS.md](docs/prd/rba-policy-sentiment/TASKS.md) — phased, dependency-ordered task plan. Work top to bottom.
3. [PRD.md](docs/prd/rba-policy-sentiment/PRD.md) — full detail. Open a specific section **only when you start the task that needs it**.

**How work is driven here:**
- A requirement's **acceptance criteria are its Definition of Done.** Tasks link to requirement IDs (FR-### / NFR-###); find those criteria in PRD §8 / §9 and make them pass before checking the box.
- **Expand high-level tasks into sub-tasks when you pick them up,** not before. Tasks in TASKS.md are intentionally coarse.
- **Work milestone by milestone** (M0 → M1 → M2 → M3). M0 is a **hard gate** (see Accuracy gate below) — do not ship publicly until it passes.
- When a requirement is ambiguous, check the PRD; if still unclear, **ask the owner rather than assume scope.**

## Intended architecture (what you're building toward)

A two-part, **static-first** system (PRD §7, §10):

- **Python batch scorer** (separate, *manually triggered* — no always-on service). Ingests each RBA monetary-policy **decision media release** (post-2020 backfill + each new one) and scores it with a **reconciled hybrid ensemble**: an LLM sentence classifier, a fine-tuned transformer (FinBERT-style), and a transparent finance/hawkish-dovish lexicon each score independently, then reconcile into one result. Inter-model disagreement becomes the **confidence** signal. Output per statement: a net dovish↔hawkish score **plus inflation / growth / employment sub-scores**, every component's result, the reconciliation, the evidence-phrase spans, and the pinned engine version.
- **Next.js front end on Vercel** (free tier). Serves **precomputed JSON/CSV** — the heavy lifting is the offline scorer, not the site. Key surfaces: a "Latest decision" hero, a stance-over-time line chart (with cash-rate overlay), a statement detail view exposing the full granular breakdown, a methodology page, CSV export, and a full-record table that also serves as the accessible chart fallback.

**Core data model:** a `decision` entity (id, date, outcome, cash_rate_target, source_url, short_quote) 1:1 with a `score` (net + inflation/growth/employment sub-scores, per-component LLM/transformer/lexicon results, reconciliation, confidence, evidence-phrase spans, engine_version, scored_at).

A separate engineering **design doc** (parser robustness, ensemble + reconciliation logic, storage, deployment) is marked TBD in the PRD and should be written before the build.

**Design language:** inherit the owner's existing RBA Board Vote Tracker (rba-tracker.vercel.app) — warm `#f4f3ee` palette, light/dark mode, editorial/plain-language tone, transparency-first footer.

## Hard constraints — do not violate these

These override default behavior and are the spine of the product (quality and transparency are the north star, **not** traffic):

- **Never persist or republish full RBA statement text.** Fetch text only to score it; store/show only **short evidence quotes** and always **link to the canonical rba.gov.au source.** (Licensing — NFR-011, FR-001.)
- **Reproducibility:** compute each score **once and persist it**; pin/cache LLM calls so re-scoring the same text + engine version is deterministic; record the **engine version per score.** (NFR-002.)
- **Accuracy gate (M0):** scores must reach **≥85% agreement (or ≥0.8 rank correlation)** vs an expert/human-labelled benchmark **before any public launch.** (NFR-004.)
- **Free-tier hosting only** (Vercel front end; scoring as an offline batch job). (NFR-009.)
- **Every published score ships its full granular breakdown** — net + sub-scores, per-component results, reconciliation, confidence, highlighted evidence phrases. (FR-011.)
- **Honor the non-goals** (HANDOFF / PRD §4): decision media releases only (no minutes/SoMP/speeches), RBA only (no Fed/ECB/RBNZ), no market/news/social sentiment, **no forecasting**, **no financial advice/trading signals**, no user accounts/alerts, **no attributing tone to individual board members.** Anything not stated as in-scope is out of scope — do not infer scope from omission.
- **Keep disclaimers visible:** "not financial advice" and "independent — not an official RBA product."
