"""Composite engine version (design §6/§10, plan step 18).

``engine_version`` is a hash of every constituent that can change a score: the
lexicon file hash, the LLM model+prompt version, the transformer revision, and
the reconciliation-config version. Stamped on every score and written to
``data/engine_version.json`` with its parts spelled out, so the run is auditable
and ``score`` can skip work whose version is unchanged (compute-once, NFR-002).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rba_scorer.paths import ENGINE_VERSION_PATH
from rba_scorer.storage.json_store import write_json_atomic

# Bump when the reconciliation logic/config changes (e.g. weighting scheme).
RECONCILE_VERSION = "reconcile-v1"


def compose_engine_version(parts: dict[str, str]) -> str:
    """A short, stable hash over the sorted constituent versions."""
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    return f"engine-2026.06-{digest}"


def engine_version_record(
    component_versions: dict[str, str],
    *,
    reconcile_version: str = RECONCILE_VERSION,
) -> dict[str, Any]:
    """Build the ``{engine_version, components}`` record persisted for auditability.

    ``component_versions`` maps each *active* component name to its pinned version
    (so a lexicon+LLM subset run yields a different composite than the full
    ensemble). The reconciliation-config version is folded in so any blend change
    moves the composite too."""
    parts = {**component_versions, "reconcile": reconcile_version}
    return {"engine_version": compose_engine_version(parts), "components": parts}


def write_engine_version(record: dict[str, Any], path: Path = ENGINE_VERSION_PATH) -> None:
    write_json_atomic(path, record)
