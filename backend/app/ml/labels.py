"""Canonical label sets and task metadata for the JurisScan-AI ML pipeline.

This module is deliberately dependency-free (standard library only) so it can be
imported by scripts, the training pipeline and the backend without pulling in
PyTorch or Transformers.

The label sets mirror the pilot dataset design (``docs/DESIGN.md``): 25 clause
categories and three risk levels (LOW / MEDIUM / HIGH). Treat these tuples as
the single source of truth for label encoding order.
"""

from __future__ import annotations

# 25 approved clause categories, in a stable alphabetical order. The order fixes
# the integer ids used by the trained classifier checkpoints.
CLAUSE_CATEGORIES: tuple[str, ...] = (
    "ARBITRATION",
    "ASSIGNMENT_AND_SUBCONTRACTING",
    "AUDIT_AND_ACCESS_RIGHTS",
    "CONFIDENTIALITY",
    "CONSENT_AND_AUTHORIZATION",
    "CONSUMER_RIGHTS_AND_REFUNDS",
    "DATA_PRIVACY",
    "DISPUTE_RESOLUTION",
    "EMPLOYMENT_AND_COMPENSATION",
    "FORCE_MAJEURE",
    "INDEMNIFICATION",
    "INTELLECTUAL_PROPERTY",
    "JURISDICTION_AND_GOVERNING_LAW",
    "LIABILITY",
    "NON_COMPETE_AND_NON_SOLICITATION",
    "NOTICE_PERIOD",
    "OTHER",
    "PAYMENT_AND_FEES",
    "PAYMENT_DEFAULT_AND_LATE_FEES",
    "PENALTIES_AND_LIQUIDATED_DAMAGES",
    "RENEWAL_AND_AUTO_RENEWAL",
    "RENTAL_AND_TENANCY",
    "SERVICE_LEVELS_AND_DELIVERABLES",
    "TERMINATION",
    "WARRANTIES_AND_REPRESENTATIONS",
)

RISK_LABELS: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH")

# Registered classification tasks: name -> ordered output labels.
TASK_LABELS: dict[str, tuple[str, ...]] = {
    "category": CLAUSE_CATEGORIES,
    "risk": RISK_LABELS,
}

# Dataset field that provides the ground-truth label for each task.
LABEL_FIELDS: dict[str, str] = {
    "category": "clause_category",
    "risk": "risk_level",
}

# The only input feature. Answer-derived fields (risk_reason, legal_reference,
# risk_type, legal_reference_status, notes, ...) must never be used as inputs.
TEXT_FIELD: str = "clause_text"

# Base pretrained encoder for both tasks.
MODEL_NAME: str = "law-ai/InLegalBERT"

TASKS: tuple[str, ...] = tuple(TASK_LABELS)


def task_labels(task: str) -> tuple[str, ...]:
    """Return the ordered output labels for ``task`` (``category`` | ``risk``)."""

    try:
        return TASK_LABELS[task]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Unknown task {task!r}. Expected one of {sorted(TASK_LABELS)}."
        ) from exc


def label_field(task: str) -> str:
    """Return the dataset field holding the ground-truth label for ``task``."""

    try:
        return LABEL_FIELDS[task]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"Unknown task {task!r}. Expected one of {sorted(LABEL_FIELDS)}."
        ) from exc


def label2id(labels: tuple[str, ...] = CLAUSE_CATEGORIES) -> dict[str, int]:
    return {label: index for index, label in enumerate(labels)}


def id2label(labels: tuple[str, ...] = CLAUSE_CATEGORIES) -> dict[int, str]:
    return {index: label for index, label in enumerate(labels)}


__all__ = [
    "CLAUSE_CATEGORIES",
    "RISK_LABELS",
    "TASK_LABELS",
    "LABEL_FIELDS",
    "TEXT_FIELD",
    "MODEL_NAME",
    "TASKS",
    "task_labels",
    "label_field",
    "label2id",
    "id2label",
]
