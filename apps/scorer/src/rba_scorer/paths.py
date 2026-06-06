"""Canonical filesystem paths for the scorer.

The scorer lives in ``apps/scorer`` but writes its published output to the
repo-root ``data/`` directory — the JSON/CSV contract the web app consumes.
"""

from __future__ import annotations

from pathlib import Path

SCORER_ROOT = Path(__file__).resolve().parents[2]  # apps/scorer
REPO_ROOT = SCORER_ROOT.parents[1]  # repo root (RBA/)

# Published output (the contract).
DATA_DIR = REPO_ROOT / "data"
EXPORTS_DIR = DATA_DIR / "exports"
BENCHMARK_DIR = DATA_DIR / "benchmark"
DECISIONS_PATH = DATA_DIR / "decisions.json"
SCORES_PATH = DATA_DIR / "scores.json"
ENGINE_VERSION_PATH = DATA_DIR / "engine_version.json"

# Caches (opposite git policies — see .gitignore and the design doc §10).
RAW_CACHE_DIR = SCORER_ROOT / ".cache" / "raw"  # gitignored: holds full page text
LLM_CACHE_DIR = SCORER_ROOT / "cache" / "llm"  # committed: structured responses only
