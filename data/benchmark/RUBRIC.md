# RBA Policy Sentiment — Labelling Rubric (net hawkish↔dovish)

| Field | Value |
| ----- | ----- |
| Purpose | Define how to assign each RBA decision a **net stance label** on a 5-point scale, consistently and reproducibly. |
| Used by | The M0 validation benchmark (NFR-004). Your labels are the **ground truth** the engine is measured against. |
| Scope | **Net stance only.** Sub-scores (inflation / growth / employment) are *not* hand-labelled in M0 — they're checked qualitatively. |
| Companion file | [`labels.csv`](labels.csv) — one row per decision; you fill the `net_label` column. |
| Source material | The decision **media release** only (linked per row). Not minutes, not the SoMP, not speeches, not news/market commentary. |

This guide is part of the audit trail: anyone can read it and understand exactly what each label means. It later seeds the public methodology page (FR-007).

---

## 1. What you are scoring

A single number capturing **how hawkish or dovish the decision media release reads** — the monetary-policy *lean* the statement communicates.

- **Hawkish (positive)** = tightening-leaning: inflation is the dominant worry; the Board sounds inclined to raise rates or hold them high/longer; emphasis on doing more to bring inflation down.
- **Dovish (negative)** = easing-leaning: growth/jobs (or disinflation) is the dominant theme; the Board sounds inclined to cut or to support the economy; emphasis on risks to activity.
- **Neutral (zero)** = genuinely balanced: two-sided risks, comfortable to wait, no directional tilt.

**Score the language and forward guidance — not the mechanical rate action.** The rate move is context, not the label:
- A **hold** can be *hawkish* (rate unchanged, but "prepared to raise further if needed") or *dovish* (rate unchanged, but "the case for easing is building").
- A **cut** delivered with a "we're not done easing" tone is more dovish than a cut framed as a one-off "fine-tuning."

Read the statement through three lenses (these inform one holistic net call):

| Lens | Hawkish signals | Dovish signals |
| ---- | --------------- | -------------- |
| **Inflation** | too high / persistent / broad-based; *upside* risks; "not yet sustainably back in the band" | moderating / returning to target; *downside* risks; "confidence growing" |
| **Growth / activity** | strong demand; economy resilient; needs restraint | subdued / slowing; weak demand; needs support |
| **Employment / labour** | tight labour market; wage pressures; full employment as a risk | softening; rising unemployment; labour market easing |

**Mind negations and qualifiers** — they flip or soften polarity:
> "inflation is **no longer** elevated" → dovish · "the Board is **not ruling out** a further increase" → hawkish · "**some** easing **may** become appropriate" → mildly dovish.

---

## 2. The 5-point scale

`net_label` is one of: **`-1`, `-0.5`, `0`, `0.5`, `1`** (write `0.5` for +0.5; the sign is only needed for the dovish side).

| Label | Stance | The release reads as… |
| :---: | ------ | --------------------- |
| **`1`** | **Strongly hawkish** | Clear tightening bias. Inflation dominates and is framed as too high / persistent with upside risks; signals further increases are likely or "more work to do"; little weight on growth/jobs downside. |
| **`0.5`** | **Mildly hawkish** | Net hawkish but qualified. Inflation still above target and the main risk, *but* progress acknowledged; retains a tightening bias or explicitly keeps the door open to a further increase. The classic **"hawkish hold."** |
| **`0`** | **Neutral / balanced** | Risks explicitly two-sided and balanced; comfortable to hold and wait; data-dependent with **no** directional tilt; inflation seen returning to target on the current path. |
| **`-0.5`** | **Mildly dovish** | Net dovish but qualified. Growing confidence inflation is returning to target; rising attention to growth/employment downside; opens the door to easing or signals cuts "may become appropriate." A **"dovish hold"** or a cautious first cut. |
| **`-1`** | **Strongly dovish** | Clear easing bias. Growth/jobs downside or disinflation dominates; delivers or signals stimulus/support; emergency easing. |

Pick the **single best** bucket. When torn between two adjacent buckets, let the **forward guidance** (what the Board says about *next* steps) break the tie. (The benchmark counts an adjacent bucket as agreement — see §5 — so don't agonise over ±0.5 boundaries, but **do** get the lean direction right.)

---

## 3. Worked examples (calibration anchors)

These calibrate the endpoints and the "tone ≠ action" idea. They are illustrations — **every decision is yours to judge from its own release.**

- **`-1` Strongly dovish** — the **2020 emergency-easing** releases (e.g. the March 2020 cuts and the November 2020 cut toward a 0.10% cash rate with support measures). The statement is dominated by downside risk and the need to support the economy.
- **`1` Strongly hawkish** — the **rapid 2022 tightening** releases (e.g. the mid-2022 +50 bp increases). Inflation is high and rising, and the Board stresses further increases will be needed.
- **`0.5` Mildly hawkish (tone vs. action)** — a **hold** that leaves the cash rate unchanged *but* stresses inflation is still too high and the Board "is not ruling out a further increase." Action = hold; lean = up → `0.5`.
- **`0` Neutral** — a **hold** where risks are called "broadly balanced" and the Board is "well placed" to wait, with no tilt up or down.
- **`-0.5` Mildly dovish** — a **first cut** (or a hold) framed around growing confidence that inflation is returning to target and increasing attention to a softening labour market, without committing to a full easing cycle.

---

## 4. How to label

1. Open the decision's release via the `source_url` in its `labels.csv` row and read it for the **policy lean** across the three lenses.
2. Decide the **direction** first (hawkish / neutral / dovish), then the **strength** (full vs. half step).
3. Enter the value in `net_label`. Optionally jot the 1–2 phrases that drove your call in `note` (this feeds residual analysis and the methodology page).
4. **Label independently:** do this *before* looking at any engine score, and ignore market reaction / hindsight — judge the statement as written.
5. **Stay consistent:** label in one or a few sittings; at the end, re-skim a handful of your early labels to check for drift.

**Edit only `net_label` and (optionally) `note`.** The other columns are read-only context.

---

## 5. How your labels are used (NFR-004)

- The corpus is split with a **seeded, deterministic** random split: ~⅔ **dev** (used to tune the lexicon / prompt / weights) and ~⅓ **locked test** (scored once, at the gate). The harness keeps them physically separate so tuning never touches the test set.
- **Primary gate (pre-registered):** **within-one-bucket agreement ≥ 85%** on the held-out test set. The engine's net is binned to this 5-point scale; it "agrees" if it lands in your bucket *or an adjacent one*.
- **Corroborating (reported, not the switch):** **Spearman rank correlation ≥ 0.8** between the engine's raw net and your labels.
- Both numbers are always published; the deciding metric is fixed in advance to prevent cherry-picking. **M0 does not ship publicly until this gate passes.**

---

## 6. Licensing (NFR-011)

Never paste full statement text into `labels.csv` or this rubric. If you use the `note` field, keep it to **short verbatim phrases (≤ ~15 words)** — the same standard the engine's evidence quotes follow. The canonical text always lives at `rba.gov.au` via the `source_url`.
