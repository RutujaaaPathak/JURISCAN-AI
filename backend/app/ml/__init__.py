"""Reusable, standalone ML utilities for JurisScan-AI.

This package holds label constants, dataset/split helpers, metric helpers and a
lightweight inference wrapper around fine-tuned InLegalBERT checkpoints. Heavy
dependencies (PyTorch, Transformers, scikit-learn) are imported lazily so that
importing ``app.ml`` never requires the ML extras.

The package is intentionally decoupled from the rule-based analyzer and is not
wired into any production API route yet.
"""

from __future__ import annotations

from app.ml.data import (
    REQUIRED_FIELDS,
    DatasetError,
    group_aware_split,
    load_jsonl,
)
from app.ml.labels import (
    CLAUSE_CATEGORIES,
    LABEL_FIELDS,
    MODEL_NAME,
    RISK_LABELS,
    TASK_LABELS,
    TEXT_FIELD,
)

__all__ = [
    "CLAUSE_CATEGORIES",
    "RISK_LABELS",
    "TASK_LABELS",
    "LABEL_FIELDS",
    "TEXT_FIELD",
    "MODEL_NAME",
    "REQUIRED_FIELDS",
    "DatasetError",
    "load_jsonl",
    "group_aware_split",
]
