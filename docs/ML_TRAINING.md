# JurisScan-AI — InLegalBERT Training Pipeline

Status: **isolated pilot pipeline**. It is not wired into the production API and
does not replace the current rule-based analyzer. Everything here is for
validating the approach on the synthetic 100-record pilot.

## 1. Task summary

Two independent sequence-classification experiments, both initialised from
[`law-ai/InLegalBERT`](https://huggingface.co/law-ai/InLegalBERT):

| Task | Output classes | Dataset label field |
|---|---|---|
| `category` | 25 clause categories | `clause_category` |
| `risk` | LOW / MEDIUM / HIGH | `risk_level` |

Only `clause_text` is used as input. Answer-derived fields (`risk_reason`,
`legal_reference`, `legal_reference_status`, `risk_type`, `affected_party`,
`context_required`, `notes`, ...) are **never** used as features.

## 2. Environment setup

The project already has a virtual environment at the repository root
(`.venv`). Use it — do not create `backend\.venv`. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-ml.txt
```

`requirements-ml.txt` installs `torch`, `transformers`, `scikit-learn` and
`numpy` only. The backend runtime (`requirements.txt`) imports nothing from
PyTorch/Transformers at startup.

## 3. Dataset validation (no model required)

```powershell
.\.venv\Scripts\python.exe scripts\validate_dataset.py --data data\jurisscan_pilot_v0.1.jsonl
```

The validator checks: JSONL parsing, required fields, unique ids, valid 25/3
label values, missing values, category and risk counts, exact duplicate clause
texts, presence of both label sets, and the pilot's "synthetic/unreviewed"
invariants. It exits non-zero on invalid data and never modifies the dataset.
A JSON report can be emitted with `--report <path>`.

## 4. Dry-run (splitting only, no download/training)

```powershell
.\.venv\Scripts\python.exe scripts\train_inlegalbert.py --task risk --validate-only
.\.venv\Scripts\python.exe scripts\train_inlegalbert.py --task category --validate-only
```

Loads the dataset, builds the deterministic group-aware splits, writes split and
label metadata under `models\`, prints the per-split plan and stops before any
model download or training.

## 5. Training

```powershell
# Smoke test defaults (3 epochs, deterministic seed, CPU) — do NOT trust metrics
.\.venv\Scripts\python.exe scripts\train_inlegalbert.py --task risk
.\.venv\Scripts\python.exe scripts\train_inlegalbert.py --task category
```

Important CLI options (see `--help` for the full list):

| Option | Default | Purpose |
|---|---|---|
| `--task` | `category` | `category` or `risk` |
| `--epochs` | 3 | Number of training epochs |
| `--batch-size` | 8 | Batch size |
| `--learning-rate` | 2e-5 | AdamW learning rate |
| `--max-length` | 256 | Max token length (clauses are 12–63 words) |
| `--seed` | 42 | Random seed for reproduciblity |
| `--device` | `auto` | `auto` / `cpu` / `cuda` |
| `--patience` | 2 | Early stopping on validation macro-F1 |
| `--class-weight` | `sqrt_inverse` | `none` / `inverse` / `sqrt_inverse` |
| `--stratify` | off | Attempt group-aware label stratification |
| `--output-dir` | `models` | Where checkpoints/metadata are written |

Class weights: `inverse` sets `w_c = N / (n_classes * count_c)`; `sqrt_inverse`
uses the square root of that. Both equal 1.0 for uniform classes and dampen
over-represented classes. Justification: the 25 category classes have 2–5
examples each, so raw inverse weights can make a 2-example class dominate;
`sqrt_inverse` is the conservative default.

### Splitting

Splits are always **group-aware**: all records sharing a `split_group_id` go in
the same split (the pilot has 95 groups; 5 of them contain contrast pairs).
~70/15/15 targets are allocated deterministically from the seeded, shuffled
group list. `--stratify` tries to stratify groups by their label set; when a
stratum is too small (default: fewer than 6 groups) it is **explicitly disabled**
and the reason is recorded in `split.json` rather than silently producing a
degenerate split. With 25 categories and 2–5 examples each, stratification for
`category` is expected to fall back.

### Training behaviour

- Fixed seeds for `random`, `numpy`, and PyTorch.
- Best checkpoint (highest validation macro-F1) is saved and reloaded before
  test evaluation.
- Test is evaluated **once**, never used for model selection.
- `fp16` is used automatically on CUDA; disabled on CPU (`--no-fp16` to disable).

## 6. Evaluation

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_inlegalbert.py --task risk --split test
.\.venv\Scripts\python.exe scripts\evaluate_inlegalbert.py --task category --split test
```

Loads the fine-tuned checkpoint and the saved `split.json`, scores the requested
split (default `test`), and writes accuracy, macro/weighted F1, per-class
precision/recall/F1, a confusion matrix, a per-record predictions CSV and a
`classification_report` text file.

## 7. Checkpoint locations

Outputs for task `<task>` land under `models\inlegalbert_<task>\`:

```
models\
└── inlegalbert_<task>\
    ├── best\                        # HF checkpoint (model + tokenizer)
    │   ├── model.safetensors
    │   ├── config.json
    │   ├── tokenizer.json / vocab.txt ...
    │   └── label_map.json           # id2label / label2id (+ task metadata)
    ├── label_map.json
    ├── split.json                   # deterministic group-aware split + record indices
    ├── training_history.json
    ├── training_args.json           # in best/
    ├── metrics.json                 # test-set metrics (after training)
    ├── confusion_matrix.csv
    ├── test_predictions.csv
    ├── classification_report.txt
    └── eval_<split>_*.{json,csv,txt} # written by evaluate_inlegalbert.py
```

These outputs are covered by `.gitignore` (`models/inlegalbert_*/` and
`models/*.safetensors`) and are regenerable.

## 8. CPU / GPU considerations

- The pipeline runs on CPU out of the box. A 3-epoch smoke run of `risk` on the
  100-record pilot takes roughly a few minutes on a modern CPU (InLegalBERT is a
  ~110M-parameter BERT; all sequences are short).
- `--device auto` selects CUDA only when `torch.cuda.is_available()` is true,
  and enables fp16 mixed precision then. The repository's current environment is
  CPU-only (`torch 2.8.0+cpu`, no CUDA).
- For any meaningful training beyond the smoke test, provision a GPU (or use
  parameter-efficient fine-tuning / a smaller model). With such a tiny dataset,
  a GPU will not improve the *quality* of results — it only shortens wall time.

## 9. Reusable inference code

`backend/app/ml/` provides dependency-light helpers:

- `labels.py` — canonical label sets (single source of truth).
- `data.py` — JSONL loading and group-aware splitting.
- `metrics.py` — scikit-learn metric wrappers.
- `predictor.py` — `TaskPredictor` / `load_predictor(task, ...)` for loading a
  fine-tuned checkpoint and running inference. PyTorch/Transformers are imported
  lazily so the backend application never imports them at startup.

Example:

```python
from app.ml.predictor import load_predictor

predictor = load_predictor("risk", models_root="models")
result = predictor.predict_one(
    "The Company may terminate this Agreement at any time for convenience..."
)
print(result.label, result.confidence, result.scores)
```

**Not wired into the API.** The rule-based analyzer remains the production path
until the ML classifiers clear review.

## 10. Limitations of the 100-record synthetic pilot (do not rely on these metrics)

- **Tiny, synthetic, unreviewed.** 100 AI-authored clauses; every record is
  `SYNTHETIC_UNREVIEWED`; `risk_reason` labels were authored alongside the text
  (label noise is possible and unmeasured).
- **Impossible stratification for `category`.** 25 classes with 2–5 examples
  each cannot be stratified into train/val/test; `--stratify` falls back for
  `category` (recorded in `split.json`). Some categories will be absent from
  validation/test splits entirely.
- **~15-record validation and test splits.** Early stopping and reported test
  metrics are extremely noisy. Many per-class precision/recall numbers are
  meaningless at this size.
- **Contrast-pair design.** Records within a `split_group_id` are near-duplicates
  by construction; group-aware splitting mitigates leakage but the 5 shared
  groups mean ~10 records share a thematic pair.
- **Single jurisdiction and no verified law.** All records are Indian and none
  cite verified legal references. The model learns to mimic this pilot, not to
  do legal analysis.
- **No legal reference as input.** `legal_reference`/`risk_reason` are never
  used, so the classifier reasons from clause wording alone by design.
- **Scope:** the pipeline validates plumbing (download, tokenization, splitting,
  training loop, metrics) on the pilot. Treat any reported F1 as a pipeline
  smoke signal only, and re-train on a vetted, larger dataset before any
  product decision.