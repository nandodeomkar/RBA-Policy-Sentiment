# RBA Policy Sentiment — Pluggable Transformer Model Layer (Implementation Plan)

| Field | Value |
| ----- | ----- |
| Status | Ready to execute |
| Date | 2026-06-07 |
| Design | [2026-06-07-rba-pluggable-transformer-models-design.md](../specs/2026-06-07-rba-pluggable-transformer-models-design.md) |
| Scope | The M0 transformer component only — make the model swappable + wire the non-gated interim Fed model live |
| Branch | `feat/m0-scorer` (code + these docs) |

Dependency-ordered. Each step lists its **done** condition. 🧑 marks a **human-in-the-loop checkpoint**. This plan executes the deferred "wire the transformer" work (M0 plan step 16) on top of the now-approved pluggable design.

**Already in place** (from the wiring spike before the pivot): the `transformer` extra is installed (torch 2.12 CPU + transformers 5.x); `pyproject.toml` `addopts` deselects integration tests by default (`-q -m 'not integration'`); a draft integration test exists in `tests/test_transformer.py` (to be reworked in step 3). Caches are warm: 75 raw pages + 64 committed LLM responses, so a re-score needs no network beyond the one-time model download.

---

## Phase A — Pluggable model layer (offline code)

1. **Add `score/transformer_models.py`** — the `TransformerModel` frozen dataclass (`name`, `model_id`, `revision`, `label_map`, `max_tokens`, `version()`); a `REGISTRY` with `fed-stance` (active; `gtfintechlab/model_federal_reserve_system_stance_label` @ `7695c0ae…`, verified label map `{LABEL_0:neutral, LABEL_1:hawkish, LABEL_2:dovish, LABEL_3:neutral}`) and `fomc-roberta` (`gtfintechlab/FOMC-RoBERTa` @ `aa3bc428…`, label map marked unverified/verify-on-access); `ACTIVE_MODEL_NAME = "fed-stance"`; `active_model()` honouring the `RBA_TRANSFORMER_MODEL` env override.
   - *Done:* importable; `active_model()` returns `fed-stance`; the env override switches the active model; an unknown name raises an error listing the registry keys.
2. **Refactor `score/transformer.py` to be model-agnostic** — drop the module-level `MODEL_NAME` / `DEFAULT_REVISION` / `LABEL_MAP`; resolve the active adapter; build the pipeline from `adapter.model_id` / `adapter.revision` (truncation `adapter.max_tokens`); apply `adapter.label_map`, **summing** probabilities of labels that share a polarity; `component_version()` returns `active_model().version()`; keep `TransformerUnavailableError`, the injectable `classifier` seam, and the `score_text(text, *, classifier=None, …)` signature. Add the startup self-check: when building the real classifier, assert `config.id2label` is fully covered by `label_map` (skipped on the injected/mock path).
   - *Done:* no model-identity constants remain in `transformer.py`; `score_text` with an injected classifier returns the correct net; the real path raises a clear error if the model's labels aren't covered.
3. **Update `tests/test_transformer.py`** — make the mock tests adapter-aware; add a 4-class label-map case and a summed-polarity case; assert `component_version()` reflects the active adapter (incl. under an env override via monkeypatch); cover the unknown-model selection error; **rework the integration test** to score via the active adapter (remove the `DEFAULT_REVISION` / private-builder references from step-5's draft).
   - *Done:* `uv run pytest` is green with the integration test deselected; the new branches are covered.
4. **Document the override in `.env.example`** — add `# RBA_TRANSFORMER_MODEL=fed-stance  # optional: override the active transformer (see registry)`.
   - *Done:* `.env.example` documents the variable; `uv run pytest` still reports `1 deselected`.

## Phase B — Validate live 🧑 (model download authorized — M0 plan step 16)

5. **Run the offline unit suite** — confirm Phase A is sound without any model.
   - *Done:* all unit tests pass; integration deselected.
6. **Run the integration test** — `uv run pytest -m integration` downloads the Fed model once and exercises the real active adapter.
   - *Done:* the integration test passes (contract shape/range + hawkish ≥ dovish ordering) against the live model.
7. **Smoke-test one real decision** — score the most recent decision's statement text (cache-first fetch) through the live transformer; sanity-check the net's sign/magnitude against that decision's known stance.
   - *Done:* net is finite, in range, and directionally plausible; result noted.

## Phase C — Re-score & verify

8. **Full ensemble run** — `uv run rba-scorer score`. The new composite `engine_version` (now including `transformer = fed-stance:7695c0ae…`) triggers a re-score of all 64: transformer live on CPU, lexicon + LLM from their committed caches, raw pages cache-first.
   - *Done:* 64 decisions scored; `data/engine_version.json` records the new composite + the transformer's `name:revision`; every record in `data/scores.json` has a `transformer` component.
9. **Determinism + FR-011 + provenance check** — re-run `uv run rba-scorer score` (no `--force`); confirm a byte-identical no-op (all reused). Confirm every score carries net + sub-scores + all three components + reconciliation + confidence + evidence (FR-011) and a `rba.gov.au` `source_url` (NFR-006).
   - *Done:* second run reuses all 64; FR-011 fields present for every decision; 0 missing `source_url`.
10. **Lint & format** — `uv run ruff check .` and `uv run ruff format .`.
    - *Done:* both clean.

## Phase D — Docs & status

11. **Update status docs** — in `TASKS.md`, mark the transformer wired via the pluggable slot with the interim Fed model; note that Fed→RBA transfer validation and the accuracy gate (NFR-004) remain **deferred** pending owner labels, and that the model's CC-BY-NC-SA attribution lands on the M1 methodology page (FR-007). Point M0 plan step 16 at this plan.
    - *Done:* `TASKS.md` reflects reality; the step-16 reference resolves.

---

## Human-in-the-loop checkpoints

| When | What |
| ---- | ---- |
| Step 6 | First run downloads the Fed stance model (RoBERTa-base) — authorized (M0 plan step 16: "OK to install torch + download locally on first run"). |
| Future | Swap the active model to the RBA-specific or FOMC-RoBERTa model once gated HF access is granted **and** its `label_map` is verified from `config.id2label` on first authenticated load. One-line change to `ACTIVE_MODEL_NAME` (or the env override). |
| Deferred | Owner labels `labels.csv` → the accuracy gate (NFR-004) quantifies Fed→RBA transfer and decides whether to keep, down-weight, or swap the transformer. |

## Out of scope (per design §12)

Multiple simultaneous transformers; per-model net functions; a general component-plugin system; a CLI model-selection flag; any change to reconciliation, lexicon, LLM, ingestion, or the benchmark harness.
