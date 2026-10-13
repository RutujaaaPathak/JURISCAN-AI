"""Reusable InLegalBERT inference for the trained JurisScan-AI classifiers.

PyTorch and Transformers are imported lazily inside :meth:`TaskPredictor.load`,
so the backend application can import ``app.ml`` without the ML extras being
installed. This module is intentionally isolated from the rule-based analyzer
and is not wired into any production route yet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from app.ml.labels import MODEL_NAME, TASKS, task_labels

# Repository root: backend/app/ml/predictor.py -> parents[3] == JURISCAN-AI/
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODELS_ROOT = _REPO_ROOT / "models"


def task_dir_name(task: str) -> str:
    """Directory name used for a task's checkpoints under ``models/``."""

    return f"inlegalbert_{task}"


def default_model_dir(task: str, models_root: str | Path | None = None) -> Path:
    root = Path(models_root) if models_root is not None else DEFAULT_MODELS_ROOT
    return root / task_dir_name(task) / "best"


@dataclass(slots=True)
class Prediction:
    label: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)


def resolve_device(preference: str = "auto"):
    """Resolve ``auto``/``cpu``/``cuda`` to a ``torch.device``.

    ``auto`` selects CUDA only when it is actually available; otherwise CPU.
    """

    import torch

    preference = (preference or "auto").lower()
    if preference == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if preference == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available on this machine.")
    return torch.device(preference)


class TaskPredictor:
    """Loads a fine-tuned checkpoint and predicts labels for clause text."""

    def __init__(self, task: str, model, tokenizer, labels: Sequence[str], device, max_length: int = 256) -> None:
        self.task = task
        self.model = model
        self.tokenizer = tokenizer
        self.labels = list(labels)
        self.device = device
        self.max_length = max_length

    @classmethod
    def load(
        cls,
        task: str,
        model_dir: str | Path | None = None,
        *,
        models_root: str | Path | None = None,
        device: str = "auto",
        max_length: int = 256,
    ) -> "TaskPredictor":
        if task not in TASKS:
            raise ValueError(f"Unknown task {task!r}. Expected one of {list(TASKS)}.")

        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        directory = Path(model_dir) if model_dir is not None else default_model_dir(task, models_root)
        if not directory.exists():
            raise FileNotFoundError(
                f"No checkpoint for task {task!r} at {directory}. Train one first."
            )

        label_map_path = directory / "label_map.json"
        if label_map_path.exists():
            mapping = json.loads(label_map_path.read_text(encoding="utf-8"))
            ordered = sorted(mapping["label2id"].items(), key=lambda item: item[1])
            labels = [label for label, _ in ordered]
        else:  # Fall back to the canonical label order.
            labels = list(task_labels(task))

        resolved = resolve_device(device)
        tokenizer = AutoTokenizer.from_pretrained(str(directory))
        model = AutoModelForSequenceClassification.from_pretrained(str(directory))
        model.to(resolved)
        model.eval()
        return cls(task, model, tokenizer, labels, resolved, max_length=max_length)

    def predict(self, texts: Sequence[str], batch_size: int = 16) -> list[Prediction]:
        import torch

        results: list[Prediction] = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = list(texts[start : start + batch_size])
                encoded = self.tokenizer(
                    batch,
                    truncation=True,
                    padding=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                ).to(self.device)
                logits = self.model(**encoded).logits
                probabilities = torch.softmax(logits, dim=-1).cpu()
                for row in probabilities:
                    index = int(torch.argmax(row).item())
                    scores = {
                        label: round(float(row[i]), 6) for i, label in enumerate(self.labels)
                    }
                    results.append(
                        Prediction(
                            label=self.labels[index],
                            confidence=round(float(row[index]), 6),
                            scores=scores,
                        )
                    )
        return results

    def predict_one(self, text: str) -> Prediction:
        return self.predict([text])[0]


def load_predictor(
    task: str,
    model_dir: str | Path | None = None,
    *,
    models_root: str | Path | None = None,
    device: str = "auto",
    max_length: int = 256,
) -> TaskPredictor:
    """Convenience wrapper around :meth:`TaskPredictor.load`."""

    return TaskPredictor.load(
        task, model_dir, models_root=models_root, device=device, max_length=max_length
    )


__all__ = [
    "Prediction",
    "TaskPredictor",
    "load_predictor",
    "resolve_device",
    "default_model_dir",
    "task_dir_name",
    "MODEL_NAME",
    "DEFAULT_MODELS_ROOT",
]
