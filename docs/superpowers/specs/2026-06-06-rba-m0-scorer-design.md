# RBA Policy Sentiment — Milestone 0 Engineering Design

| Field | Value |
| ----- | ----- |
| Status | Approved (ready for implementation planning) |
| Date | 2026-06-06 |
| Owner | Omkar |
| Scope | **Milestone 0 only** — data ingestion + reconciled hybrid ensemble scorer + validation benchmark |
| Fulfils | The "Design doc [TBD]" referenced in [PRD §10](../../prd/rba-policy-sentiment/PRD.md) |
| Source of truth | [PRD.md](../../prd/rba-policy-sentiment/PRD.md) · [TASKS.md](../../prd/rba-policy-sentiment/TASKS.md) · [HANDOFF.md](../../prd/rba-policy-sentiment/HANDOFF.md) |

---

## 1. Scope & context

This document is the engineering design for **Milestone 0 — Data + engine**, the hard gate of the RBA Policy Sentiment project. M0 must, per [PRD §11](../../prd/rba-policy-sentiment/PRD.md):

> ingest post-2020 RBA decision statements; build the reconciled hybrid ensemble; and have scores meet the §3 accuracy guardrail on a benchmark.

M0 is purely backend/data. **No web front end is built in M0** (that is M1). The deliverable is a Python batch job that produces the precomputed JSON/CSV dataset the static site will later consume, plus a benchmark that proves the scores clear the accuracy bar.

**Requirements implemented here:** FR-001 (ingestion), FR-002 (ensemble scoring), FR-011 (full granular breakdown — the data shape), NFR-002 (reproducibility), NFR-004 (accuracy gate), NFR-006 (provenance), NFR-011 (licensing).

**Decisions locked during brainstorming (2026-06-06):**
1. **LLM provider:** Anthropic Claude, default model **Haiku 4.5** (`claude-haiku-4-5-…`), escalate to a larger model only if the benchmark demands it.
2. **Benchmark:** owner self-labels the **full** post-2020 corpus on a 5-point net scale; ~⅓ held out as a locked test set; sub-scores validated qualitatively (not labelled) for MVP.
3. **Build strategy:** iterative, baseline-first — benchmark harness first, then lexicon → +LLM → +transformer, measuring agreement at each layer.
4. **Transformer:** FOMC-RoBERTa, contributing to the **net score only** (it is not dimension-aware).
5. **Lexicon:** a curated, version-controlled hawkish/dovish term list we build (not a repurposed generic finance-sentiment list).
6. **Reconciliation:** equal weights by default; confidence = 1 − normalized inter-component disagreement.
7. **Accuracy gate:** **pre-registered** — primary = within-one-bucket agreement ≥85% on held-out; Spearman rank correlation reported alongside as corroboration (a deliberate, slightly stricter reading of the PRD's "or").

---

## 2. Architecture overview

Two halves connected by a file contract. M0 builds the left half; the right half is M1.

```
RBA/
├─ apps/
│  ├─ scorer/                    # Python batch job  ← THIS MILESTONE
│  │  ├─ src/rba_scorer/
│  │  │  ├─ ingest/              # fetch + parse RBA pages → decisions
│  │  │  ├─ score/
│  │  │  │  ├─ lexicon.py        # curated hawkish/dovish lexicon scorer
│  │  │  │  ├─ llm.py            # Claude sentence-level scorer (cached)
│  │  │  │  ├─ transformer.py    # FOMC-RoBERTa net scorer (local)
│  │  │  │  └─ reconcile.py      # blend + confidence + evidence merge
│  │  │  ├─ benchmark/           # split, metrics, gate, report
│  │  │  ├─ io/                  # JSON/CSV writers, caches, atomic writes
│  │  │  └─ cli.py               # ingest / score / benchmark / export
│  │  ├─ data/lexicon/           # versioned lexicon source (committed)
│  │  ├─ cache/llm/              # structured LLM responses (COMMITTED — see §10)
│  │  ├─ .cache/raw/             # raw fetched HTML (GITIGNORED — see §5)
│  │  ├─ tests/
│  │  ├─ pyproject.toml
│  │  └─ .env                    # ANTHROPIC_API_KEY (GITIGNORED)
│  └─ web/                       # (M1 — not created in M0)
├─ data/                         # PUBLISHED OUTPUT = the contract with the site
│  ├─ decisions.json
│  ├─ scores.json
│  ├─ exports/scores.csv
│  ├─ engine_version.json
│  └─ benchmark/
│     ├─ labels.csv              # owner's 5-point labels
│     ├─ RUBRIC.md               # labelling guide (drafted in M0)
│     └─ benchmark_report.{md,json}
└─ docs/                         # PRD, specs (exists)
```

**The contract.** `data/*.json` + `data/exports/scores.csv` are the sole interface between the scorer and the future site. The site reads them statically; nothing else couples the two halves.

---

## 3. Tech stack

- **Python 3.11+**, environment/deps via **`uv`** (fast on Windows; plain `pip` + `pyproject.toml` also works).
- **`ruff`** for lint + format; **`pytest`** for tests.
- **Ingestion:** `httpx`/`requests` + `BeautifulSoup` (lenient HTML parsing).
- **LLM:** official `anthropic` SDK, structured output, `temperature=0`.
- **Transformer:** `transformers` + `torch` (CPU is fine — batch job, ~50 short docs), model `gtfintechlab/FOMC-RoBERTa` (pinned revision).
- **Config:** `ANTHROPIC_API_KEY` via `.env` (never committed).

---

## 4. Data model & storage

Flat, committed JSON — no database. ~40-50 records makes a DB pure overhead; JSON is diffable, free, reproducible, and directly servable by the static site.

**Score scale.** Net ∈ **[−1, +1]**: −1 = maximally dovish, 0 = neutral, +1 = maximally hawkish. Sub-scores use the same range. Owner's 5-point labels map to {−1, −0.5, 0, +0.5, +1}.

**`decision`** (`data/decisions.json`, array) — no full statement text, ever:
```json
{
  "id": "2024-05-07",
  "date": "2024-05-07",
  "title": "Statement by the Reserve Bank Board: Monetary Policy Decision",
  "source_url": "https://www.rba.gov.au/media-releases/2024/mr-24-09.html",
  "outcome": { "action": "hold", "change_bps": 0 },
  "cash_rate_target": 4.35
}
```

**`score`** (`data/scores.json`, keyed by `decision_id`) — the full granular breakdown (FR-011):
```json
{
  "decision_id": "2024-05-07",
  "net": 0.25,
  "sub_scores": { "inflation": 0.50, "growth": -0.10, "employment": 0.20 },
  "confidence": 0.88,
  "components": {
    "lexicon":     { "net": 0.30, "sub_scores": {"inflation":0.5,"growth":-0.2,"employment":0.1}, "matched_terms": ["upside risks to inflation"], "version": "lex-v1:<hash>" },
    "llm":         { "net": 0.20, "sub_scores": {"inflation":0.5,"growth":0.0,"employment":0.3}, "rationale": "…", "model_id": "claude-haiku-4-5-…" },
    "transformer": { "net": 0.25, "model_revision": "<hf-revision-hash>" }
  },
  "reconciliation": { "method": "equal_weight_mean", "weights": {"lexicon":0.333,"llm":0.333,"transformer":0.334}, "disagreement": 0.12 },
  "evidence_phrases": [
    { "text": "upside risks to inflation", "polarity": "hawkish", "dimension": "inflation", "source": ["llm","lexicon"] },
    { "text": "growth has been subdued",   "polarity": "dovish",  "dimension": "growth",    "source": ["llm"] }
  ],
  "engine_version": "engine-2026.06-<composite-hash>",
  "scored_at": "2026-06-06T03:21:00Z"
}
```

`data/engine_version.json` records the composite version and its constituent parts (lexicon hash, LLM model id, transformer revision, reconciliation-config version) for auditability.

---

## 5. Ingestion pipeline (FR-001)

**Sources.**
- **Decisions** — the RBA monetary-policy decisions index (`rba.gov.au/monetary-policy/int-rate-decisions/`) enumerates decisions; each links to its media release, fetched for statement text + outcome.
- **Cash rate target** — RBA's machine-readable cash-rate-target series, parsed for `cash_rate_target` at each decision date (also seeds the M2 overlay).

**Flow:** `fetch → cache raw → parse → validate → upsert`.
- **Raw cache (`apps/scorer/.cache/raw/`, gitignored).** Every fetched page is snapshotted locally. Avoids re-hitting RBA on re-runs, makes the parser testable against saved pages, and — critically — keeps full statement HTML/text **local and uncommitted** so the repository never carries full text (NFR-011).
- **Parse → `decision`.** Extract `date`, `title`, `source_url`, `outcome` (hold/hike/cut + bps), `cash_rate_target`. Full text lives in memory only long enough to be scored; only decision metadata and (post-scoring) short evidence phrases are persisted.
- **Cross-validation.** The parsed outcome (hold/hike/cut) is cross-checked against the change in the cash-rate-target series; a mismatch is an error, not a silent write.
- **Idempotent upsert.** Keyed by date-slug `id`; re-runs update in place, never duplicate. Writes are **atomic** (write-temp-then-rename) so a mid-run failure cannot corrupt the existing dataset.

**Robustness (R-003).** The RBA moved to the Monetary Policy Board (2025) and statement formats drift. The parser validates that each expected field was actually extracted and **fails loudly with the offending URL** rather than writing nulls — a format change surfaces as a clear error on the next run.

---

## 6. Scoring engine (FR-002, FR-011)

Every component emits the same shape — `net` + `{inflation, growth, employment}` on [−1, +1] — so outputs are directly comparable and reconcilable. Built in the agreed order.

**1. Lexicon (deterministic baseline, $0).** Sentence-split the statement; match a curated, version-controlled hawkish/dovish term list (terms tagged by dimension) with simple negation handling (e.g. "inflation is *no longer* elevated" flips polarity). Net = normalized (hawkish − dovish) signal; sub-scores from dimension-tagged matches. Emits matched phrases as evidence. Pure function. *Version = hash of the lexicon source file.*

**2. LLM (Claude Haiku, `temperature=0`).** Sentence-level classification (per PRD §7): each sentence → dimension + polarity + intensity via a structured-output call, aggregated to net + sub-scores. The model returns **only short verbatim evidence phrases (≤ ~15 words)** plus a one-line rationale — never the full statement, keeping the cache licensing-clean. Every response cached to disk keyed by `hash(model_id + prompt + sentence/text)`; re-runs and tests never re-call the API. *Version = pinned model id.*

**3. Transformer (FOMC-RoBERTa, local).** Per-sentence hawkish/dovish/neutral probabilities → mapped to net ∈ [−1, +1] and aggregated. **Net only** — not dimension-aware, so it does not produce sub-scores; documented as a methodology limitation. Runs in eval mode with pinned weights → deterministic. *Version = pinned model revision.*

**Reconciliation (`reconcile.py`).**
- **Net** = equal-weighted mean of the three component nets. (If any weight tuning is ever done, it is a single coarse, documented knob fit on the dev split only — never the test set.)
- **Sub-scores** = reconciled from the two dimension-aware components (lexicon + LLM); the transformer does not contribute here.
- **Confidence** = 1 − normalized disagreement across the three component nets (agreement → high; divergence → low). This is the honest uncertainty signal US-5 wants.
- **Evidence phrases** merged across components, deduplicated, tagged with polarity + dimension + which component(s) flagged them.
- **All** component raw outputs, weights, and disagreement are persisted (FR-011) — nothing is a black box.

**Determinism & `engine_version` (NFR-002).** `engine_version` = composite hash of {lexicon hash, LLM model id, transformer revision, reconciliation-config version}. Same text + same `engine_version` → byte-identical score (LLM via cache; lexicon/transformer/reconcile are pure/pinned). **Compute-once-and-persist:** an existing score is reused unless its `engine_version` differs or `--force` is passed.

---

## 7. Benchmark & validation (NFR-004)

**Labels.** `data/benchmark/labels.csv` — `decision_id`, `net_label` ∈ {−1, −0.5, 0, +0.5, +1}, optional `note`. A `RUBRIC.md` (drafted in M0) defines what pushes a statement into each bucket, with worked examples, so labelling is consistent and the benchmark is itself auditable/reproducible.

**Split.** Seeded, deterministic random split: ~⅓ locked **test**, ~⅔ **dev**. The harness keeps them physically separate — prompt/lexicon/weight tuning reads dev only; the test set is scored once, at the gate. Because the test set is small, leave-one-out on dev is also reported as a stability check.

**Metrics & pre-registered gate.**
- **Primary gate:** within-one-bucket agreement **≥85%** on held-out test (engine net binned to the 5-point scale; counts as agreement if it matches the owner's bucket or an adjacent one).
- **Corroborating (reported, not the switch):** Spearman rank correlation (target ≥0.8) between engine net (raw) and labels.
- Both numbers are always published. The metric that decides pass/fail is fixed in advance to prevent post-hoc cherry-picking.

**Report.** `benchmark_report.{md,json}`: headline metrics, per-decision residuals (largest engine-vs-owner divergences — the tuning signal), and **per-component agreement** so the iterative build shows what lexicon → +LLM → +transformer each contributes. This artifact later seeds the public methodology page (FR-007).

---

## 8. Testing strategy

- **Parser** tested against saved page fixtures, trimmed/synthetic to stay licensing-clean.
- **Determinism test:** score a fixture twice → byte-identical output (guards NFR-002).
- **Lexicon & reconciliation** are pure functions → direct unit tests with synthetic inputs (incl. negation cases and disagreement → confidence).
- **LLM and transformer** sit behind interfaces; unit tests use cached/mock responses — **no live API calls or model downloads in the suite**. One optional, separately-marked integration test exercises the real model when credentials/weights are available.
- **Benchmark harness** tested for correct dev/test isolation and correct metric computation on toy data.

---

## 9. Error handling & reliability

- Parser fails loud with the URL on any missing/unparseable field (R-003).
- All dataset writes are atomic; a bad run never corrupts good data.
- LLM client retries with backoff; errors clearly if a response is uncached **and** no API key is present (so the determinism contract is never silently violated).
- A single failed decision is skipped-and-logged, not fatal to the batch.

---

## 10. Determinism & reproducibility (NFR-002) — consolidated

- **Pinned everything:** dependency lockfile, LLM model id, transformer revision, seeded benchmark split, versioned lexicon.
- **Two caches, opposite policies:**
  - `apps/scorer/.cache/raw/` — raw fetched HTML — **gitignored** (full text; licensing).
  - `apps/scorer/cache/llm/` — structured LLM responses (scores + short phrases + rationale, no full text) — **committed**, so any third party can reproduce every score without an API key (directly serves NFR-002/003).
- **`engine_version` stamped on every score**; re-running the same text under the same version reproduces the stored score exactly.

---

## 11. Out of scope for M0 (and non-goals)

- **No web front end** (M1), **no cash-rate overlay UI** (M2), **no CSV-download UI** — though M0 *does* emit `scores.csv` as part of the contract.
- Reaffirming PRD §4 non-goals: decision media releases only (no minutes/SoMP/speeches), RBA only, no market/news sentiment, no forecasting, no financial advice, no accounts, no per-board-member attribution, **no full-text storage**.

---

## 12. Definition of done (M0 exit criteria)

| # | Criterion | Traces to |
| - | --------- | --------- |
| 1 | All post-2020 decision releases ingested once, idempotently, with no full text persisted | FR-001 |
| 2 | Each decision scored: net + 3 sub-scores, all three component outputs, reconciliation, confidence, evidence phrases, engine_version | FR-002, FR-011 |
| 3 | Re-scoring the same text + engine_version is byte-identical | NFR-002 |
| 4 | Owner labels complete; held-out test passes the pre-registered gate (within-one-bucket agreement ≥85%); rank correlation reported | NFR-004 |
| 5 | Every score carries its canonical `rba.gov.au` source URL | NFR-006 |
| 6 | `data/` contract (decisions.json, scores.json, exports/scores.csv, engine_version.json, benchmark_report) is produced and committed | (site contract) |

Per [HANDOFF.md](../../prd/rba-policy-sentiment/HANDOFF.md), **M0 is a hard gate**: the project does not proceed to public-facing work until criterion 4 passes.

---

## 13. Open items to validate during implementation

- **RBA page structure** — exact selectors/format of the decisions index, media-release pages, and the cash-rate-target file to be confirmed during the M0 ingestion spike (drives parser detail).
- **Published-label scan** — a quick check for any existing academic hawkish/dovish labels for post-2020 RBA decisions; assume none and self-label, but confirm.
- **FOMC-RoBERTa transfer** — validate that the Fed-trained model gives a usable cross-institution signal on RBA text; if it actively hurts net agreement on the dev split, document and consider down-weighting (still equal-weight by default).
- **Lexicon coverage** — the curated term list will be iterated against dev-set residuals; initial list seeded from central-bank hawkish/dovish literature cited in the methodology references.
