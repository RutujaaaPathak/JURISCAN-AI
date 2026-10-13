"""Dataset loading and deterministic, group-aware splitting utilities.

The pilot dataset stores one JSON object per line with 16 fields. Related or
contrast-pair clauses share a ``split_group_id``; every record in a group must
land in the same train/validation/test split to avoid leakage.

This module is standard-library only so it can be used by the validation,
training and evaluation scripts without importing PyTorch.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Sequence

# All 16 fields, in the order the pilot generator emits them.
REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "clause_text",
    "clause_category",
    "risk_level",
    "risk_reason",
    "affected_party",
    "risk_type",
    "jurisdiction",
    "contract_type",
    "context_required",
    "legal_reference",
    "legal_reference_status",
    "review_status",
    "generation_source",
    "split_group_id",
    "notes",
)

# Fields that are legitimately null/empty for the synthetic pilot.
NULLABLE_FIELDS: frozenset[str] = frozenset({"legal_reference", "notes"})

GROUP_FIELD = "split_group_id"

SPLITS: tuple[str, ...] = ("train", "val", "test")


class DatasetError(ValueError):
    """Raised when the dataset cannot be parsed or is structurally invalid."""


def load_jsonl(path: str | Path) -> list[dict]:
    """Parse a JSONL file, raising :class:`DatasetError` with line context."""

    path = Path(path)
    if not path.exists():
        raise DatasetError(f"Dataset not found: {path}")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise DatasetError(
                    f"Line {line_number}: invalid JSON ({exc.msg})."
                ) from exc
            if not isinstance(obj, dict):
                raise DatasetError(f"Line {line_number}: expected a JSON object.")
            records.append(obj)
    if not records:
        raise DatasetError(f"Dataset is empty: {path}")
    return records


def group_records(records: Sequence[dict], group_field: str = GROUP_FIELD) -> dict[str, list[int]]:
    """Map each group id to the sorted indices of its records."""

    groups: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        group = record.get(group_field)
        if not group:
            raise DatasetError(
                f"Record {record.get('id', index)!r} is missing {group_field!r}."
            )
        groups[str(group)].append(index)
    return {group: sorted(indices) for group, indices in groups.items()}


def _allocate_targets(total: int, ratios: Sequence[float]) -> dict[str, int]:
    """Split ``total`` items across splits using largest-remainder rounding."""

    raw = [ratio * total for ratio in ratios]
    floors = [int(value) for value in raw]
    remainder = total - sum(floors)
    order = sorted(range(len(ratios)), key=lambda i: (raw[i] - floors[i]), reverse=True)
    for i in range(remainder):
        floors[order[i % len(floors)]] += 1
    return {name: floors[i] for i, name in enumerate(SPLITS)}


def group_aware_split(
    records: Sequence[dict],
    label_field: str,
    *,
    ratios: Sequence[float] = (0.70, 0.15, 0.15),
    seed: int = 42,
    stratify: bool = True,
    min_groups_per_stratum: int = 6,
    group_field: str = GROUP_FIELD,
) -> tuple[dict[str, list[int]], dict]:
    """Deterministically split record indices, keeping groups intact.

    Returns ``(splits, metadata)`` where ``splits`` maps split name to record
    indices and ``metadata`` records the parameters, per-split label coverage
    and any stratification fallback. Stratification is attempted on the set of
    labels inside each group; if any stratum is too small to fill three splits
    (``min_groups_per_stratum``) it is explicitly disabled and recorded rather
    than silently producing a degenerate split.
    """

    groups = group_records(records, group_field)
    group_ids = sorted(groups)
    total_groups = len(group_ids)

    group_labels = {
        group: frozenset(str(records[i][label_field]) for i in indices)
        for group, indices in groups.items()
    }

    metadata: dict = {
        "seed": seed,
        "ratios": list(ratios),
        "group_field": group_field,
        "label_field": label_field,
        "total_groups": total_groups,
        "requested_stratify": stratify,
        "stratify": False,
        "stratify_fallback_reason": None,
    }

    rng = random.Random(seed)
    assignment: dict[str, str] = {}

    if stratify:
        strata: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for group in group_ids:
            strata[tuple(sorted(group_labels[group]))].append(group)
        small = {key: len(value) for key, value in strata.items() if len(value) < min_groups_per_stratum}
        if small:
            metadata["stratify_fallback_reason"] = (
                "Stratification infeasible: "
                f"{len(small)} of {len(strata)} strata have fewer than "
                f"{min_groups_per_stratum} groups (min group count "
                f"{min(small.values())}). Falling back to an unstratified "
                "group-aware split; per-class labels may be unevenly covered."
            )
            stratify = False
        else:
            metadata["stratify"] = True
            metadata["stratum_count"] = len(strata)

    targets = _allocate_targets(total_groups, ratios)
    remaining = dict(targets)

    def _choose_split() -> str:
        # Pick the split with the largest remaining deficit; ties fall back to
        # split order (train, val, test) for determinism.
        best = max(SPLITS, key=lambda name: (remaining[name], -SPLITS.index(name)))
        remaining[best] -= 1
        return best

    if stratify:
        strata = defaultdict(list)
        for group in group_ids:
            strata[tuple(sorted(group_labels[group]))].append(group)
        for key in sorted(strata):
            bucket = sorted(strata[key])
            rng.shuffle(bucket)
            for group in bucket:
                assignment[group] = _choose_split()
    else:
        bucket = list(group_ids)
        rng.shuffle(bucket)
        for group in bucket:
            assignment[group] = _choose_split()

    splits: dict[str, list[int]] = {name: [] for name in SPLITS}
    for group, indices in groups.items():
        splits[assignment[group]].extend(indices)
    for name in SPLITS:
        splits[name].sort()

    metadata["group_targets"] = targets
    metadata["groups_per_split"] = {
        name: sum(1 for group in group_ids if assignment[group] == name) for name in SPLITS
    }
    metadata["records_per_split"] = {name: len(splits[name]) for name in SPLITS}
    metadata["label_coverage"] = {
        name: dict(
            sorted(
                Counter(str(records[i][label_field]) for i in splits[name]).items()
            )
        )
        for name in SPLITS
    }
    metadata["group_ids"] = {
        name: sorted(group for group in group_ids if assignment[group] == name)
        for name in SPLITS
    }
    return splits, metadata


def summarize_label_coverage(
    records: Sequence[dict], indices: Iterable[int], label_field: str
) -> dict[str, int]:
    return dict(sorted(Counter(str(records[i][label_field]) for i in indices).items()))


__all__ = [
    "REQUIRED_FIELDS",
    "NULLABLE_FIELDS",
    "GROUP_FIELD",
    "SPLITS",
    "DatasetError",
    "load_jsonl",
    "group_records",
    "group_aware_split",
    "summarize_label_coverage",
]
