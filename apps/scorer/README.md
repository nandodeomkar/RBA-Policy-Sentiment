# RBA Policy Sentiment — Scorer (Milestone 0)

Offline batch job that ingests RBA monetary-policy **decision media releases** and
scores each with a **reconciled hybrid ensemble** (curated lexicon + Claude +
FOMC-RoBERTa). It emits the precomputed JSON/CSV under the repo-root `data/`
directory that the (future) Next.js site consumes.

Design: [`docs/superpowers/specs/2026-06-06-rba-m0-scorer-design.md`](../../docs/superpowers/specs/2026-06-06-rba-m0-scorer-design.md) ·
Plan: [`docs/superpowers/plans/2026-06-06-rba-m0-implementation-plan.md`](../../docs/superpowers/plans/2026-06-06-rba-m0-implementation-plan.md)

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Run from this directory:

```powershell
uv sync                       # install core + dev dependencies (no PyTorch)
Copy-Item .env.example .env   # then add your ANTHROPIC_API_KEY (needed from step 15)
```

The transformer component (FOMC-RoBERTa) pulls in PyTorch and is installed
separately, only when needed:

```powershell
uv sync --extra transformer
```

## Commands

```powershell
uv run rba-scorer --help            # list subcommands
uv run rba-scorer ingest            # fetch + parse decisions -> ../../data/decisions.json
uv run rba-scorer score             # run the ensemble    -> ../../data/scores.json
uv run rba-scorer benchmark         # evaluate vs labels  (the M0 accuracy gate)
uv run rba-scorer export            # write               ../../data/exports/scores.csv

uv run pytest                       # tests — no network, no model downloads
uv run pytest -m integration        # opt-in live-model / API tests
uv run ruff check .                 # lint
uv run ruff format .                # format
```

> **Phase A:** the subcommands are wired but not yet implemented — they log a
> notice and exit cleanly. Implementation proceeds per the plan (Phases B–E).
