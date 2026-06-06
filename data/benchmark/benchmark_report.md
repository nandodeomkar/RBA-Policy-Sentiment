# RBA Policy Sentiment — Benchmark Report

_Generated 2026-06-06T12:49:44+00:00 · engine `engine-2026.06-d8acadec`_

> **Not the live gate of record unless the corpus is fully labelled and scored.**

## Gate (NFR-004)

**❌ FAIL** — primary metric: within-one-bucket agreement on the held-out test set.

| Metric | Value | Target |
| ------ | ----- | ------ |
| Within-one-bucket (test) | n/a | ≥ 85.0% (decides) |
| Spearman (test) | n/a | ≥ 0.80 (corroborating) |
| Test set size | 0 | — |
| Stability (95% bootstrap CI) | n/a – n/a | — |

## Coverage

- Decisions labelled: **0** · scored: **64**
- Split (seed `20260606`, test fraction 0.333): **43** dev / **21** test

## Agreement by component (within-one-bucket / Spearman)

| Estimator | Dev (n) | Test (n) |
| --------- | ------- | -------- |
| reconciled | n/a / n/a (0) | n/a / n/a (0) |
| lexicon | n/a / n/a (0) | n/a / n/a (0) |
| llm | n/a / n/a (0) | n/a / n/a (0) |

## Largest residuals (engine vs. owner)

| Decision | Split | Label | Engine net | Bucket | |Δ| | Within 1 |
| -------- | ----- | ----- | ---------- | ------ | --- | -------- |
| _(no scored + labelled decisions yet)_ | | | | | | |
