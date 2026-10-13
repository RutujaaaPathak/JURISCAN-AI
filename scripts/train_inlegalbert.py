#!/usr/bin/env python3
"""Fine-tune ``law-ai/InLegalBERT`` for one JurisScan-AI classification task.

Two independent experiments are supported via ``--task``:

* ``category`` - classify clause text into 25 clause categories.
* ``risk``     - classify clause text into LOW / MEDIUM / HIGH risk.

Only ``clause_text`` is used as input. Answer-derived fields (``risk_reason``,
``legal_reference``, ``risk_type``, ``notes``, ...) are never used as features.

Splits are deterministic and group-aware: every record sharing a
``split_group_id`` stays in the same split, so contrast/paraphrase families
cannot leak across splits. Stratification is attempted on the group label set
and explicitly disabled (with a recorded reason) when a stratum is too small.

The defaults are tuned for a tiny CPU smoke test on the 100-record pilot. The
resulting metrics must NOT be treated as production performance.

Usage
-----
    .venv/Scripts/python.exe scripts/train_inlegalbert.py --task category
    .venv/Scripts/python.exe scripts/train_inlegalbert.py --task risk

    # Skip everything except data loading/splitting (no model download):
    .venv/Scripts/python.exe scripts/train_inlegalbert.py --task risk --validate-only
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections import Counter
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.ml.data import DatasetError, group_aware_split, load_jsonl  # noqa: E402
from app.ml.labels import (  # noqa: E402
    LABEL_FIELDS,
    MODEL_NAME,
    TEXT_FIELD,
    label2id,
    task_labels,
)
from app.ml.metrics import (  # noqa: E402
    classification_report_text,
    compute_classification_metrics,
    write_confusion_matrix_csv,
    write_json,
    write_predictions_csv,
)

DEFAULT_DATA = _REPO_ROOT / "data" / "jurisscan_pilot_v0.1.jsonl"
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "models"


def _torch():
    return importlib.import_module("torch")


def _transformers():
    return importlib.import_module("transformers")


def set_seed(seed: int) -> None:
    torch = _torch()
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def resolve_device(preference: str):
    torch = _torch()
    preference = (preference or "auto").lower()
    if preference == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    elif preference == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("--device cuda requested but CUDA is not available.")
        device = torch.device("cuda")
    elif preference == "cpu":
        device = torch.device("cpu")
    else:
        raise ValueError(f"Unsupported device: {preference!r}")
    print(f"Device: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))
    return device


def class_weight_vector(train_labels, n_classes: int, mode: str):
    """Return a per-class loss weight tensor, or None when mode == 'none'.

    * ``inverse``       - w_c = N / (n_classes * count_c)
    * ``sqrt_inverse``  - w_c = sqrt(N / (n_classes * count_c))

    Both equal 1.0 when classes are perfectly uniform and reduce the pull of
    over-represented classes. Classes with zero training examples get weight 0
    removed-pull semantics replaced by a neutral 1.0 (safe: their loss term is
    never selected as the target).
    """

    if mode == "none":
        return None
    torch = _torch()
    counts = Counter(train_labels)
    total = len(train_labels)
    weights = []
    for index in range(n_classes):
        count = counts.get(index, 0)
        if count == 0:
            weights.append(1.0)
        elif mode == "inverse":
            weights.append(total / (n_classes * count))
        elif mode == "sqrt_inverse":
            weights.append((total / (n_classes * count)) ** 0.5)
        else:
            raise ValueError(f"Unsupported class-weight mode: {mode!r}")
    return torch.tensor(weights, dtype=torch.float32)


def tokenize_split(tokenizer, records, indices, text_field, max_length):
    texts = [str(records[i][text_field]) for i in indices]
    return tokenizer(
        texts,
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="pt",
    )


def fidelity_options(records, splits):
    """Return per-split text/behaviour alignment info for the split metadata."""

    report = {}
    for name in ("train", "val", "test"):
        texts = [records[i][TEXT_FIELD] for i in splits[name]]
        words = [len(str(t).split()) for t in texts]
        report[name] = {
            "n": len(texts),
            "word_min": min(words) if words else 0,
            "word_max": max(words) if words else 0,
        }
    return report


def run_epoch(
    model,
    optimizer,
    scheduler,
    criterion,
    data,
    label_ids,
    device,
    batch_size,
    *,
    train: bool,
    grad_clip: float | None,
    fp16: bool,
):
    """Run one pass over an encoded split.

    ``data`` is the batched tokenizer output whose rows correspond one-to-one
    with ``label_ids``; batches are drawn by position so predictions always
    align with the ground-truth label ids.
    """

    torch = _torch()
    import numpy as np

    model.train() if train else model.eval()
    random_state = np.random.RandomState(0)  # fixed tile ordering for reproducibility
    order = random_state.permutation(len(label_ids)) if train else np.arange(len(label_ids))

    total_loss = 0.0
    n_seen = 0
    all_logits = []

    for start in range(0, len(order), batch_size):
        batch = [int(index) for index in order[start : start + batch_size]]
        input_ids = data["input_ids"][batch].to(device)
        attention_mask = data["attention_mask"][batch].to(device)
        labels = torch.tensor([label_ids[i] for i in batch], dtype=torch.long).to(device)

        use_amp = fp16 and device.type == "cuda"
        context = torch.autocast(device_type="cuda", dtype=torch.float16) if use_amp else _nullcontext()
        with torch.set_grad_enabled(train), context:
            logits = model(input_ids=input_ids, attention_mask=attention_mask).logits
            loss = criterion(logits, labels)

        if train:
            optimizer.zero_grad()
            loss.backward()
            if grad_clip is not None:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
            if scheduler is not None:
                scheduler.step()

        total_loss += float(loss.item()) * len(batch)
        n_seen += len(batch)
        if not train and device.type == "cuda":
            all_logits.append(logits.detach().cpu())
        elif not train:
            all_logits.append(logits.detach())

    if train:
        return total_loss / max(n_seen, 1), None, None
    logits = torch.cat(all_logits, dim=0)
    probabilities = torch.softmax(logits, dim=-1)
    prediction_ids = probabilities.argmax(dim=-1).tolist()
    confidences = probabilities.max(dim=-1).values.float().tolist()
    return total_loss / max(n_seen, 1), prediction_ids, confidences


class _nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("category", "risk"), default="category")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--model-name", default=MODEL_NAME,
        help="Pretrained checkpoint to initialise from (default: law-ai/InLegalBERT).",
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--no-fp16", action="store_true", help="Disable fp16 on CUDA.")
    parser.add_argument(
        "--patience", type=int, default=2,
        help="Early-stopping patience in epochs on validation macro-F1.",
    )
    parser.add_argument(
        "--class-weight", choices=("none", "inverse", "sqrt_inverse"), default="sqrt_inverse",
        help="Class-imbalance weighting for the training loss.",
    )
    parser.add_argument(
        "--stratify", action="store_true",
        help="Attempt group-aware label stratification; falls back and records why "
        "when a stratum is too small.",
    )
    parser.add_argument("--no-stratify", action="store_true", help="Force an unstratified group split.")
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Load the dataset, build splits and print the plan, then exit "
        "without downloading the model or training.",
    )
    args = parser.parse_args(argv)

    stratify = args.stratify and not args.no_stratify

    try:
        records = load_jsonl(args.data)
    except DatasetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    labels = task_labels(args.task)
    label_field = LABEL_FIELDS[args.task]
    l2i = label2id(labels)

    splits, split_meta = group_aware_split(
        records,
        label_field,
        seed=args.seed,
        stratify=stratify,
    )

    print(f"Task:            {args.task}")
    print(f"Records:         {len(records)}")
    print(f"Groups:          {split_meta['total_groups']}")
    print(f"Split targets:   {split_meta['group_targets']}")
    print(f"Split (groups):  {split_meta['groups_per_split']}")
    print(f"Split (records): {split_meta['records_per_split']}")
    if split_meta["stratify"]:
        print("Stratification:  enabled")
    elif split_meta["stratify_fallback_reason"]:
        print("Stratification:  disabled (fallback)")
        print(f"  Reason: {split_meta['stratify_fallback_reason']}")
    else:
        print("Stratification:  not requested")

    task_dir = Path(args.output_dir) / f"inlegalbert_{args.task}"
    task_dir.mkdir(parents=True, exist_ok=True)

    label_mapping = {
        "task": args.task,
        "model_name": args.model_name,
        "label_field": label_field,
        "text_field": TEXT_FIELD,
        "n_labels": len(labels),
        "labels": list(labels),
        "label2id": l2i,
        "id2label": {str(i): label for i, label in enumerate(labels)},
    }
    split_payload = {
        "task": args.task,
        "seed": args.seed,
        "data": str(Path(args.data).resolve()),
        "split": split_meta,
        "fidelity": fidelity_options(records, splits),
        "record_indices": {name: splits[name] for name in ("train", "val", "test")},
    }
    write_json(task_dir / "split.json", split_payload)
    write_json(task_dir / "label_map.json", label_mapping)
    print(f"Split/label metadata: {task_dir}")

    if args.validate_only:
        for name in ("train", "val", "test"):
            counts = Counter(records[i][label_field] for i in splits[name])
            print(f"  {name:6s} n={len(splits[name]):3d} labels={len(counts):2d}")
        print("validate-only: stopped before model download/training.")
        return 0

    print("Importing PyTorch / Transformers (first run may download the tokenizer "
          "and model weights)...")
    torch = _torch()
    transformers = _transformers()
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    set_seed(args.seed)
    device = resolve_device(args.device)
    use_fp16 = device.type == "cuda" and not args.no_fp16

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=len(labels)
    )
    model.config.label2id = dict(l2i)
    model.config.id2label = {str(index): label for index, label in enumerate(labels)}
    model.to(device)

    train_indices = splits["train"]
    val_indices = splits["val"]
    test_indices = splits["test"]

    train_encoding = tokenize_split(tokenizer, records, train_indices, TEXT_FIELD, args.max_length)
    val_encoding = tokenize_split(tokenizer, records, val_indices, TEXT_FIELD, args.max_length)
    test_encoding = tokenize_split(tokenizer, records, test_indices, TEXT_FIELD, args.max_length)

    train_label_ids = [l2i[str(records[i][label_field])] for i in train_indices]
    val_label_ids = [l2i[str(records[i][label_field])] for i in val_indices]
    test_label_ids = [l2i[str(records[i][label_field])] for i in test_indices]

    weights = class_weight_vector(train_label_ids, len(labels), args.class_weight)
    if weights is not None:
        print(f"Class weights ({args.class_weight}): weights[:5]={weights[:5].tolist()}")
        criteria = torch.nn.CrossEntropyLoss(weight=weights.to(device))
    else:
        print("Class weights: none")
        criteria = torch.nn.CrossEntropyLoss()

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    steps_per_epoch = max(1, (len(train_indices) + args.batch_size - 1) // args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = transformers.get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    best_val = None
    patience_left = args.patience
    best_state = None
    history = []

    print(f"\nTraining {args.task} for up to {args.epochs} epochs "
          f"(train={len(train_indices)}, val={len(val_indices)}, test={len(test_indices)}).\n")

    for epoch in range(1, args.epochs + 1):
        train_loss, _, _ = run_epoch(
            model, optimizer, scheduler, criteria, train_encoding, train_label_ids,
            device, args.batch_size, train=True, grad_clip=args.max_grad_norm, fp16=use_fp16,
        )
        val_loss, val_pred, _ = run_epoch(
            model, optimizer, scheduler, criteria, val_encoding, val_label_ids,
            device, args.batch_size, train=False, grad_clip=None, fp16=use_fp16,
        )
        val_metrics = compute_classification_metrics(val_label_ids, val_pred, labels)
        val_macro = val_metrics["macro_f1"]
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(float(train_loss), 5),
                "val_loss": round(float(val_loss), 5),
                "val_accuracy": val_metrics["accuracy"],
                "val_macro_f1": val_macro,
                "val_weighted_f1": val_metrics["weighted_f1"],
            }
        )
        print(
            f"epoch {epoch:2d}: train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
            f"val_acc={val_metrics['accuracy']:.3f} val_macro_f1={val_macro:.3f}"
        )

        if best_val is None or val_macro > best_val:
            best_val = val_macro
            patience_left = args.patience
            best_state = {name: param.detach().cpu().clone() for name, param in model.named_parameters()}
        else:
            patience_left -= 1
            if patience_left <= 0 and epoch < args.epochs:
                print(f"Early stopping at epoch {epoch} (no val macro-F1 improvement).")
                break

    if best_state is None:
        best_state = {name: param.detach().cpu().clone() for name, param in model.named_parameters()}

    model.load_state_dict(best_state)

    best_dir = task_dir / "best"
    best_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(best_dir)
    tokenizer.save_pretrained(best_dir)
    write_json(best_dir / "label_map.json", label_mapping)
    write_json(best_dir / "training_args.json", {k: str(v) for k, v in vars(args).items()})
    write_json(task_dir / "training_history.json", history)
    print(f"Best checkpoint saved to: {best_dir}")

    _, test_pred, test_conf = run_epoch(
        model, optimizer, scheduler, criteria, test_encoding, test_label_ids,
        device, args.batch_size, train=False, grad_clip=None, fp16=use_fp16,
    )
    test_metrics = compute_classification_metrics(test_label_ids, test_pred, labels)

    predictions = [
        {
            "id": records[i]["id"],
            "true_label": labels[true_id],
            "pred_label": labels[pred_id],
            "confidence": round(float(confidence), 6),
            "correct": int(true_id == pred_id),
        }
        for i, (true_id, pred_id, confidence)
        in zip(test_indices, zip(test_label_ids, test_pred, test_conf))
    ]
    write_json(task_dir / "metrics.json", test_metrics)
    write_json(task_dir / "split.json", split_payload)
    write_confusion_matrix_csv(task_dir / "confusion_matrix.csv", test_metrics["confusion_matrix"], labels)
    write_predictions_csv(task_dir / "test_predictions.csv", predictions)
    (task_dir / "classification_report.txt").write_text(
        classification_report_text(test_label_ids, test_pred, labels), encoding="utf-8"
    )

    test_metrics["best_val_macro_f1"] = round(float(best_val or 0.0), 4)
    test_metrics["n_train"] = len(train_indices)
    test_metrics["n_val"] = len(val_indices)
    test_metrics["n_test"] = len(test_indices)
    test_metrics["class_weight"] = args.class_weight
    write_json(task_dir / "metrics.json", test_metrics)

    print(f"\n=== Test-set metrics ({args.task}) ===")
    print(f"accuracy     : {test_metrics['accuracy']:.4f}")
    print(f"macro-F1     : {test_metrics['macro_f1']:.4f}")
    print(f"weighted-F1  : {test_metrics['weighted_f1']:.4f}")
    print(f"best val F1  : {test_metrics['best_val_macro_f1']:.4f}")
    print("\nNOTE: measured on the 100-record synthetic pilot only. Do NOT treat ")
    print("these numbers as production performance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())