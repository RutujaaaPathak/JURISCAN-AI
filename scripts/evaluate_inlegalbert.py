#!/usr/bin/env python3
"""Evaluate a fine-tuned InLegalBERT checkpoint against a held-out split.

Loads the checkpoint trained by ``train_inlegalbert.py`` and the deterministic
split it saved, then produces metrics, a confusion matrix and per-record
predictions for a chosen split (default ``test``).

The evaluation split is never seen during training, so these numbers are a fair
(if small-pilot) estimate of held-out behaviour.

Usage
-----
    .venv/Scripts/python.exe scripts/evaluate_inlegalbert.py --task category
    .venv/Scripts/python.exe scripts/evaluate_inlegalbert.py --task risk --split test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.ml.data import DatasetError, load_jsonl  # noqa: E402
from app.ml.labels import LABEL_FIELDS, TEXT_FIELD  # noqa: E402
from app.ml.metrics import (  # noqa: E402
    classification_report_text,
    compute_classification_metrics,
    write_confusion_matrix_csv,
    write_json,
    write_predictions_csv,
)
from app.ml.predictor import default_model_dir, load_predictor, task_dir_name  # noqa: E402

DEFAULT_DATA = _REPO_ROOT / "data" / "jurisscan_pilot_v0.1.jsonl"
DEFAULT_MODELS_ROOT = _REPO_ROOT / "models"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("category", "risk"), default="category")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument(
        "--models-root", default=str(DEFAULT_MODELS_ROOT),
        help="Root directory that holds inlegalbert_<task>/ checkpoints.",
    )
    parser.add_argument("--model-dir", default=None, help="Explicit checkpoint directory (overrides --models-root).")
    parser.add_argument("--split-file", default=None, help="Path to the split.json written by training.")
    parser.add_argument("--split", choices=("train", "val", "test"), default="test")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args(argv)

    try:
        records = load_jsonl(args.data)
    except DatasetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    task_dir = Path(args.models_root) / task_dir_name(args.task)
    split_path = Path(args.split_file) if args.split_file else task_dir / "split.json"
    if not split_path.exists():
        print(f"ERROR: split file not found: {split_path}", file=sys.stderr)
        return 2
    split_payload = json.loads(split_path.read_text(encoding="utf-8"))
    if "record_indices" in split_payload:
        indices = split_payload["record_indices"].get(args.split)
    else:  # Backward compatibility with pre-index split.json files.
        indices = split_payload["split"]["record_indices"].get(args.split)
    if indices is None:
        print(f"ERROR: split {args.split!r} not present in {split_path}", file=sys.stderr)
        return 2

    model_dir = Path(args.model_dir) if args.model_dir else default_model_dir(args.task, args.models_root)
    if not model_dir.exists():
        print(f"ERROR: checkpoint not found: {model_dir}\nRun scripts/train_inlegalbert.py first.", file=sys.stderr)
        return 2

    print(f"Task:          {args.task}")
    print(f"Split:         {args.split} ({len(indices)} records)")
    print(f"Checkpoint:    {model_dir}")

    predictor = load_predictor(
        args.task, model_dir, models_root=args.models_root, device=args.device, max_length=args.max_length
    )
    label_field = LABEL_FIELDS[args.task]
    text_field = TEXT_FIELD
    labels = predictor.labels

    texts = [str(records[i][text_field]) for i in indices]
    predictions = predictor.predict(texts, batch_size=args.batch_size)

    y_true = []
    y_pred = []
    rows = []
    for record_index, prediction in zip(indices, predictions):
        true_label = str(records[record_index][label_field])
        # Guard against a checkpoint trained on a different label order.
        try:
            true_id = labels.index(true_label)
            pred_id = labels.index(prediction.label)
        except ValueError as exc:
            print(f"ERROR: checkpoint label set does not match the dataset ({exc}).", file=sys.stderr)
            return 2
        y_true.append(true_id)
        y_pred.append(pred_id)
        rows.append(
            {
                "id": records[record_index]["id"],
                "true_label": true_label,
                "pred_label": prediction.label,
                "confidence": prediction.confidence,
                "correct": int(true_id == pred_id),
            }
        )

    metrics = compute_classification_metrics(y_true, y_pred, labels)
    report = classification_report_text(y_true, y_pred, labels)

    out_dir = Path(args.split_file).parent if args.split_file else task_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"eval_{args.split}"
    write_json(out_dir / f"{prefix}_metrics.json", metrics)
    write_confusion_matrix_csv(out_dir / f"{prefix}_confusion_matrix.csv", metrics["confusion_matrix"], labels)
    write_predictions_csv(out_dir / f"{prefix}_predictions.csv", rows)
    (out_dir / f"{prefix}_classification_report.txt").write_text(report, encoding="utf-8")

    print(f"\n=== Metrics on {args.split} split ({args.task}) ===")
    print(f"accuracy     : {metrics['accuracy']:.4f}")
    print(f"macro-F1     : {metrics['macro_f1']:.4f}")
    print(f"weighted-F1  : {metrics['weighted_f1']:.4f}")
    print(f"n_samples    : {metrics['n_samples']}")
    print(f"labels       : {metrics['labels_present']} (present) / {metrics['labels_predicted']} (predicted)")
    print(f"\nOutputs written to: {out_dir}")

    if metrics["n_samples"] < 10:
        print(
            "\nNOTE: this split is very small; metrics are noisy and category-level "
            "scores are not reliable."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())