"""Classification metric helpers shared by the training and evaluation scripts.

scikit-learn is imported lazily inside :func:`compute_classification_metrics` so
that importing the ``app.ml`` package never requires the ML extras.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Sequence


def compute_classification_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    labels: Sequence[str],
) -> dict:
    """Return accuracy, macro/weighted F1, per-class precision/recall and a
    confusion matrix.

    ``labels`` is the full ordered output label set, so metrics remain correct
    even when a split does not contain every class.
    """

    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_recall_fscore_support,
    )

    label_ids = list(range(len(labels)))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=label_ids, zero_division=0
    )
    matrix = confusion_matrix(y_true, y_pred, labels=label_ids).tolist()

    per_class = {
        labels[i]: {
            "precision": round(float(precision[i]), 4),
            "recall": round(float(recall[i]), 4),
            "f1": round(float(f1[i]), 4),
            "support": int(support[i]),
        }
        for i in range(len(labels))
    }

    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=label_ids, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_true, y_pred, labels=label_ids, average="weighted", zero_division=0)), 4),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "labels": list(labels),
        "n_samples": len(y_true),
        "labels_present": sorted({labels[i] for i in set(y_true)}),
        "labels_predicted": sorted({labels[i] for i in set(y_pred)}),
    }


def write_json(path: str | Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_confusion_matrix_csv(path: str | Path, matrix: Sequence[Sequence[int]], labels: Sequence[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\pred", *labels])
        for label, row in zip(labels, matrix):
            writer.writerow([label, *row])


def write_predictions_csv(
    path: str | Path,
    predictions: Sequence[dict],
) -> None:
    fieldnames = ["id", "true_label", "pred_label", "confidence", "correct"]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in predictions:
            writer.writerow(row)


def classification_report_text(y_true: Sequence[int], y_pred: Sequence[int], labels: Sequence[str]) -> str:
    from sklearn.metrics import classification_report

    return classification_report(
        y_true,
        y_pred,
        labels=list(range(len(labels))),
        target_names=list(labels),
        zero_division=0,
    )


__all__ = [
    "compute_classification_metrics",
    "classification_report_text",
    "write_json",
    "write_confusion_matrix_csv",
    "write_predictions_csv",
]
