"""Load and validate the owner's benchmark labels (``data/benchmark/labels.csv``).

Only the ``net_label`` column is ground truth; blank rows are unlabelled and
excluded. Any extra context columns (``date``, ``action``, ...) are ignored, so
the file can stay human-friendly for labelling. See ``data/benchmark/RUBRIC.md``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# The 5-point net scale (design §4 / RUBRIC.md). Owner labels map to these.
VALID_LABELS: tuple[float, ...] = (-1.0, -0.5, 0.0, 0.5, 1.0)

REQUIRED_COLUMNS: tuple[str, ...] = ("decision_id", "net_label")


class LabelError(ValueError):
    """A labels.csv row carries an unparseable or out-of-range ``net_label``."""


@dataclass(frozen=True)
class LabelSet:
    """The full decision universe in the file plus the labelled subset."""

    ids: tuple[str, ...]  # every decision id present (labelled or not)
    labels: dict[str, float]  # decision_id -> net_label, labelled rows only

    @property
    def labelled_ids(self) -> tuple[str, ...]:
        return tuple(self.labels)


def _parse_net_label(raw: str, decision_id: str) -> float | None:
    raw = raw.strip()
    if raw == "":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise LabelError(f"{decision_id}: net_label {raw!r} is not a number") from exc
    if value not in VALID_LABELS:
        raise LabelError(f"{decision_id}: net_label {value} not in {list(VALID_LABELS)}")
    return value


def load_labels(path: Path) -> LabelSet:
    """Read ``labels.csv`` into a :class:`LabelSet`.

    Raises :class:`LabelError` on a bad value and ``ValueError`` if a required
    column is missing.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for required in REQUIRED_COLUMNS:
            if required not in fieldnames:
                raise ValueError(f"labels.csv missing required column {required!r}")
        ids: list[str] = []
        labels: dict[str, float] = {}
        for row in reader:
            decision_id = (row.get("decision_id") or "").strip()
            if not decision_id:
                continue
            ids.append(decision_id)
            value = _parse_net_label(row.get("net_label") or "", decision_id)
            if value is not None:
                labels[decision_id] = value
    return LabelSet(ids=tuple(ids), labels=labels)
