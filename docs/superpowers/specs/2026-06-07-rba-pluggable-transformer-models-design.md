# RBA Policy Sentiment — Pluggable Transformer Model Layer (Design)

| Field | Value |
| ----- | ----- |
| Status | Approved (ready for implementation planning) |
| Date | 2026-06-07 |
| Owner | Omkar |
| Scope | The **transformer component** of the M0 ensemble only — make the model swappable and select a non-gated interim model |
| Amends | [M0 Engineering Design](2026-06-06-rba-m0-scorer-design.md) §6 "component 3" (the transformer) and decision #4 |
| Source of truth | [PRD.md](../../prd/rba-policy-sentiment/PRD.md) · [TASKS.md](../../prd/rba-policy-sentiment/TASKS.md) |

---

## 1. Scope & context

The M0 design's third ensemble component is a finance-domain transformer that scores each statement's net hawkish↔dovish stance. It was specified as **`gtfintechlab/FOMC-RoBERTa`** (net-only; design §6 component 3). That model is now **gated on Hugging Face** (HTTP 401 without granted access); the owner has requested access, but approval is pending and may take time.

This design does two things:

1. **Unblocks the build now** by selecting a non-gated interim model — `gtfintechlab/model_federal_reserve_system_stance_label`, the newer (2025) generation of the same hawkish/dovish stance task.
2. **Makes the transformer slot model-agnostic** so swapping models — to the RBA-specific or FOMC-RoBERTa model the moment gated access lands, or to anything better later — is a small, well-tested data change, not a code rewrite.

It changes **only** the transformer component. Lexicon, LLM, reconciliation, ingestion, and the benchmark harness are untouched. It implements no new requirements; it preserves the existing ones: FR-002 (ensemble scoring), FR-011 (full granular breakdown), NFR-002 (reproducibility).

**Why this is the right moment:** the M0 design already flagged the open question *"FOMC-RoBERTa transfer — validate the Fed-trained model gives a usable signal on RBA text; if it hurts, reconsider."* A swappable slot is the natural home for that contingency, and the interim model carries the **same** Fed→RBA transfer caveat the design already accepted — no new methodological risk.

## 2. Decisions locked during brainstorming (2026-06-07)

1. **Scope:** exactly **one active transformer at a time**, selected by config. Not multiple simultaneous transformers, not a general component-plugin system.
2. **Interim model:** `gtfintechlab/model_federal_reserve_system_stance_label` — a true hawkish/dovish **stance** classifier (RoBERTa-base), non-gated. Chosen over generic FinBERT *sentiment* models, which are a weak proxy for monetary-policy stance.
3. **Abstraction shape:** each model is a frozen **`TransformerModel` dataclass** in a small **registry**; one is marked active. (Rejected: subclass-per-model — needless ceremony; external JSON config — label maps belong in version-controlled, unit-tested code.)
4. **Selection:** a committed `ACTIVE_MODEL_NAME` constant (so canonical `data/` is reproducible) with an optional `RBA_TRANSFORMER_MODEL` env override for experiments.
5. **Net rule unchanged:** `mean(P(hawkish) − P(dovish))` per sentence; still **net-only**, no sub-scores, no evidence — so reconciliation is unaffected.
6. **Licensing:** the interim model is **CC-BY-NC-SA 4.0** (non-commercial); accepted for this free, non-commercial public-good site, attributed on the methodology page (FR-007). See §11.

## 3. Architecture & boundaries

```
score/
├─ transformer.py          # model-AGNOSTIC scorer: active adapter -> pipeline -> net-only ComponentResult
├─ transformer_models.py   # NEW: TransformerModel dataclass + REGISTRY + active-model resolution
├─ reconcile.py            # unchanged — already blends any net-only component
├─ engine.py               # unchanged — composes engine_version from component version strings
└─ base.py                 # unchanged — ComponentResult contract
```

The split keeps two concerns isolated:

- **`transformer.py`** owns *scoring mechanics*: build a Hugging Face `text-classification` pipeline for the active model, run the segmented sentences, map raw labels → polarity, average to a net, and return `ComponentResult(net, version, sub_scores={}, evidence=())`. It knows nothing about *which* model is active beyond what the adapter tells it. The injectable `classifier` seam and the `score_text(text, *, classifier=None, ...)` signature are preserved so the existing mock-based unit tests keep working with no live model.
- **`transformer_models.py`** owns the *model catalog*: the adapter dataclass, the registry of known models, and which one is active. Adding or swapping a model touches only this file.

`reconcile()` already filters sub-scores to dimension-aware components and computes confidence over N component nets, so a swapped net-only model needs no reconciliation change.

## 4. The adapter — `TransformerModel`

A frozen dataclass capturing everything model-specific:

```python
@dataclass(frozen=True)
class TransformerModel:
    name: str                    # short stable key, e.g. "fed-stance"
    model_id: str                # HF repo id
    revision: str                # pinned commit SHA (immutable -> reproducible)
    label_map: dict[str, str]    # raw model label -> {"hawkish","dovish","neutral"}
    max_tokens: int = 128        # truncation length (per the model card)

    def version(self) -> str:
        return f"{self.name}:{self.revision}"
```

- `label_map` keys are the model's **raw** labels (e.g. `"LABEL_0"`). Any label that is not hawkish/dovish — including a model's "irrelevant" class — maps to `"neutral"` and so contributes 0 to the net.
- `version()` is what flows into `engine_version` (see §5). Including `name` makes the composite differ between, say, `fed-stance` and `fomc-roberta` even if revisions ever collided.
- **No per-model net function.** Every model in the registry uses the single net rule in §6; this is deliberately omitted until a model actually needs a different rule (YAGNI).

## 5. Model selection & versioning (NFR-002)

- `transformer_models.py` defines `ACTIVE_MODEL_NAME = "fed-stance"` (committed) and a resolver `active_model() -> TransformerModel` that honours an optional `RBA_TRANSFORMER_MODEL` environment variable, falling back to the constant. An unknown name raises a clear error listing the registry keys.
- `transformer.component_version()` returns `active_model().version()` (e.g. `"fed-stance:7695c0ae…"`) instead of the old hardcoded `"fomc-roberta:main"`.
- `engine.py` is unchanged: it already builds `component_versions["transformer"] = transformer_component.component_version()` and hashes it into the composite `engine_version`. Therefore:
  - **Switching the active model changes `engine_version`** → compute-once re-scores honestly.
  - **Re-running the same configuration is byte-identical** (the model runs in eval mode at a pinned revision; the env override, if set, is reflected in the version string), preserving NFR-002.

## 6. Labels & net derivation

- The interim Fed model's labels (from its card): `LABEL_0 = neutral`, `LABEL_1 = hawkish`, `LABEL_2 = dovish`, `LABEL_3 = irrelevant`. Its adapter `label_map` is therefore `{"LABEL_0": "neutral", "LABEL_1": "hawkish", "LABEL_2": "dovish", "LABEL_3": "neutral"}`.
- This label order **differs** from the current hardcoded `LABEL_MAP` (which guessed `LABEL_0 = dovish`). A wrong map would invert every score — the central risk this design removes by making the map a verified per-model field.
- **Net rule (unchanged):** for each sentence, `net = P(hawkish) − P(dovish)`; the statement net is the mean over sentences, clamped to [−1, 1]. Empty text → 0. Neutral and irrelevant probabilities never enter the net, so the rule is identical for 3-class and 4-class models.
- **Summed polarity (fix):** when building per-sentence polarity probabilities, labels that map to the **same** polarity are **summed** (the current code overwrites). Net is unaffected today, but summing is the correct general behaviour.
- **Startup self-check:** when constructing the real classifier, assert the model's `config.id2label` labels are all present in the adapter's `label_map`; raise if not. This catches a model whose label set drifts before it can silently corrupt scores. The mock/test path (injected `classifier`) skips this — no download.

## 7. The registry

| name | model_id | revision | status |
| ---- | -------- | -------- | ------ |
| `fed-stance` *(active)* | `gtfintechlab/model_federal_reserve_system_stance_label` | `7695c0aebcd1a85ee23ff41df6a57b024e20f82b` | non-gated; label_map verified from model card |
| `fomc-roberta` | `gtfintechlab/FOMC-RoBERTa` | `aa3bc4281fb1fe73c8872e09ad5c64b898f90d83` | **gated**; `label_map` marked verify-on-access (cannot confirm while gated) |

`fomc-roberta` stays in the registry as the documented swap target. Its `label_map` carries an explicit "unverified — confirm `id2label` on first authenticated load" note, because its labels cannot be inspected while the repo is gated. When access lands, verifying the map and (optionally) setting `ACTIVE_MODEL_NAME = "fomc-roberta"` is the whole swap. An RBA-specific model (`model_reserve_bank_of_australia_stance_label`, also gated today) can be added the same way.

## 8. File layout & changes

- **New** `score/transformer_models.py` — `TransformerModel`, `REGISTRY`, `ACTIVE_MODEL_NAME`, `active_model()`.
- **Edit** `score/transformer.py` — remove module constants `MODEL_NAME`/`DEFAULT_REVISION`/`LABEL_MAP`; resolve the active adapter; build the pipeline from `adapter.model_id`/`adapter.revision`/`adapter.max_tokens`; apply `adapter.label_map` (summed); `component_version()` → `active_model().version()`. Keep `TransformerUnavailableError`, the `classifier` seam, and the `score_text` signature.
- **Edit** `tests/test_transformer.py` — keep the mock-based tests; make them adapter-aware; add a 4-class label-map case and a summed-polarity case; assert `component_version()` reflects the active adapter; cover the unknown-model error. The existing `@pytest.mark.integration` test now exercises the live Fed model.
- **Edit** `.env.example` — document the optional `RBA_TRANSFORMER_MODEL` override.

## 9. Testing

- **Unit (offline, default suite — no network, no download):** net math; label-map application for a 3-class and a 4-class model; summed-polarity; empty text → 0; `version()` and `component_version()` reflect the active adapter; unknown-model selection error; missing-`transformer`-extra error.
- **Integration (opt-in, `uv run pytest -m integration`):** loads the real active model and asserts contract shape/range plus a polarity ordering check (clearly hawkish text scores ≥ clearly dovish text). Deselected by default via `addopts = "-q -m 'not integration'"`.

## 10. Migration & data impact

Turning the transformer slot on (and setting the active model) changes the composite `engine_version`, so compute-once **re-scores all 64 decisions**: lexicon and LLM come from their committed caches (no API key needed), the transformer runs live on CPU. The published `data/scores.json` gains a `transformer` component for every decision (FR-011), `data/engine_version.json` records the new composite plus the transformer's `name:revision`, and re-running with no change is a byte-identical no-op (NFR-002).

## 11. Licensing

The interim model is licensed **CC-BY-NC-SA 4.0**. The project uses it for **non-commercial** inference on a free public-good site, which is within the licence; attribution is given on the methodology page (FR-007), consistent with the academic-model posture the M0 design already assumed. This is a documented acceptance, not a blanket clearance: if the project ever becomes commercial, or redistributes model weights/derivatives, the licence must be revisited. (NFR-011 governs RBA *statement text*, which is unaffected — the transformer never persists statement text.)

## 12. Scope boundaries (non-goals)

- **One** active transformer — no multi-transformer ensembling.
- **No** per-model net functions (single shared rule until a model needs otherwise).
- **No** general component-plugin system; lexicon and LLM are not pluggable by this work.
- **No** CLI flag for model selection — the committed constant plus the env override are sufficient.
- **No** change to reconciliation, confidence, ingestion, or the benchmark harness.

## 13. Open questions & future work

- **Fed→RBA transfer** remains the M0 design's open question. Quantifying it needs the owner's benchmark labels, and the **accuracy gate (NFR-004) is deferred** — so transfer is validated qualitatively for now and measured once labels exist. The swappable slot is the mitigation if transfer proves poor.
- **Gated models** (`fomc-roberta`, `model_reserve_bank_of_australia_stance_label`) become registry swaps once access is granted and their label maps are verified on first authenticated load.

## 14. Traceability

| Requirement / decision | How this design honours it |
| ---------------------- | -------------------------- |
| FR-002 (ensemble scoring) | Transformer remains the ensemble's net-only third component |
| FR-011 (full granular breakdown) | Per-decision `transformer` component + its `name:revision` version persisted |
| NFR-002 (reproducibility) | Pinned model revision; active model folded into `engine_version`; compute-once |
| NFR-011 (licensing — RBA text) | Unaffected; transformer never persists statement text |
| M0 design §6 component 3 / decision #4 | Revised: FOMC-RoBERTa → pluggable slot with a non-gated interim model |
| Implementation plan step 16 | This is the design for that step's "wire the transformer" work |
