#!/usr/bin/env python3
"""Validate the JurisScan-AI pilot dataset (structural checks only).

This script never modifies the dataset. It fails with a non-zero exit code and a
clear error list when the data is structurally invalid. It is deliberately
independent of the model/training code so validation can run with only the
Python standard library.

Example
-------
    python scripts/validate_dataset.py --data data/jurisscan_pilot_v0.1.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.ml.labels import (  # noqa: E402
    CLAUSE_CATEGORIES,
    LABEL_FIELDS,
    RISK_LABELS,
    TEXT_FIELD,
)
from app.ml.data import (  # noqa: E402
    NULLABLE_FIELDS,
    REQUIRED_FIELDS,
)

DEFAULT_DATA = _REPO_ROOT / "data" / "jurisscan_pilot_v0.1.jsonl"


def _parse_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(obj, dict):
                errors.append(f"line {line_number}: expected a JSON object")
                continue
            records.append(obj)
    return records, errors


def validate(records: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not records:
        errors.append("dataset contains no records")

    field_counts = Counter()
    for record in records:
        field_counts.update(record.keys())

    missing_fields = [f for f in REQUIRED_FIELDS if field_counts.get(f, 0) < len(records)]
    if missing_fields:
        for field in missing_fields:
            present = field_counts.get(field, 0)
            errors.append(
                f"required field {field!r} missing in {len(records) - present} record(s)"
            )
    extra_fields = sorted(set(field_counts) - set(REQUIRED_FIELDS))
    if extra_fields:
        warnings.append(f"unexpected extra field(s): {extra_fields}")

    ids = [r.get("id") for r in records]
    duplicate_ids = sorted({i for i in ids if ids.count(i) > 1})
    if duplicate_ids:
        errors.append(f"duplicate id(s): {duplicate_ids}")
    blank_ids = [i for i in ids if not i]
    if blank_ids:
        errors.append(f"{len(blank_ids)} record(s) have an empty id")

    expected_categories = set(CLAUSE_CATEGORIES)
    expected_risks = set(RISK_LABELS)
    seen_categories = set()
    seen_risks = set()
    category_counter: Counter = Counter()
    risk_counter: Counter = Counter()
    missing_values: Counter = Counter()

    for record in records:
        rid = record.get("id", "<no-id>")
        for field in REQUIRED_FIELDS:
            if field not in record:
                continue
            value = record[field]
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_values[field] += 1
                if field not in NULLABLE_FIELDS:
                    errors.append(f"{rid}: required field {field!r} is empty")

        category = record.get("clause_category")
        if category is not None:
            category_counter[str(category)] += 1
            if str(category) not in expected_categories:
                errors.append(f"{rid}: invalid clause_category {category!r}")
            seen_categories.add(str(category))

        risk = record.get("risk_level")
        if risk is not None:
            risk_counter[str(risk)] += 1
            if str(risk) not in expected_risks:
                errors.append(f"{rid}: invalid risk_level {risk!r}")
            seen_risks.add(str(risk))

        if record.get(TEXT_FIELD) is not None and not str(record[TEXT_FIELD]).strip():
            errors.append(f"{rid}: clause_text is empty")

        # Synthetic / unreviewed invariants for the pilot.
        if record.get("review_status") not in (None, "SYNTHETIC_UNREVIEWED"):
            warnings.append(
                f"{rid}: review_status={record.get('review_status')!r} "
                "(pilot is expected to be SYNTHETIC_UNREVIEWED)"
            )
        if record.get("generation_source") not in (None, "SYNTHETIC_AI"):
            warnings.append(f"{rid}: unexpected generation_source")
        if record.get("legal_reference") is not None:
            warnings.append(
                f"{rid}: legal_reference is non-null; pilot policy expects null"
            )

    if seen_risks != expected_risks:
        errors.append(
            "risk label set mismatch: expected "
            f"{sorted(expected_risks)}, found {sorted(seen_risks)}"
        )
    missing_categories = sorted(expected_categories - seen_categories)
    if missing_categories:
        errors.append(
            f"category label set mismatch: {len(missing_categories)} of "
            f"{len(expected_categories)} expected categories absent: {missing_categories}"
        )

    texts = [str(r.get(TEXT_FIELD, "")) for r in records]
    exact_duplicate_texts = sum(count - 1 for count in Counter(texts).values() if count > 1)

    return {
        "record_count": len(records),
        "field_set_matches_expected": not extra_fields and not missing_fields,
        "required_fields": list(REQUIRED_FIELDS),
        "missing_fields": missing_fields,
        "extra_fields": extra_fields,
        "missing_value_counts": dict(sorted(missing_values.items())),
        "unique_ids": len(set(ids)) == len(ids),
        "duplicate_ids": duplicate_ids,
        "valid_categories": seen_categories <= expected_categories,
        "valid_risks": seen_risks <= expected_risks,
        "expected_category_count": len(expected_categories),
        "observed_category_count": len(seen_categories),
        "missing_expected_categories": missing_categories,
        "category_counts": dict(sorted(category_counter.items())),
        "risk_counts": dict(sorted(risk_counter.items())),
        "expected_risk_labels": list(RISK_LABELS),
        "observed_risk_labels": sorted(seen_risks),
        "both_label_sets_present": seen_risks == expected_risks and len(seen_categories) > 0,
        "exact_duplicate_clause_texts": exact_duplicate_texts,
        "label_fields": dict(LABEL_FIELDS),
        "errors": errors,
        "warnings": warnings,
    }


def _print_report(report: dict) -> None:
    print(f"Records:            {report['record_count']}")
    print(f"Unique IDs:         {report['unique_ids']}")
    print(f"Categories:         {report['observed_category_count']}/{report['expected_category_count']}")
    print(f"Risk labels:        {sorted(report['observed_risk_labels'])}")
    print(f"Both label sets:    {report['both_label_sets_present']}")
    print(f"Exact dup texts:    {report['exact_duplicate_clause_texts']}")
    print(f"Missing values:     {report['missing_value_counts'] or '{}'}")
    print("\nCategory counts:")
    for category, count in report["category_counts"].items():
        print(f"  {category:40s} {count}")
    print("\nRisk counts:")
    for risk, count in report["risk_counts"].items():
        print(f"  {risk:8s} {count}")

    if report["warnings"]:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report["warnings"]:
            print(f"  - {warning}")
    if report["errors"]:
        print(f"\nERRORS ({len(report['errors'])}):")
        for error in report["errors"]:
            print(f"  - {error}")
    else:
        print("\nOK: dataset passed all structural checks.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="Path to the JSONL dataset.")
    parser.add_argument("--report", default=None, help="Optional path to write a JSON report.")
    parser.add_argument("--quiet", action="store_true", help="Only print the final status line.")
    args = parser.parse_args(argv)

    path = Path(args.data)
    if not path.exists():
        print(f"ERROR: dataset not found: {path}", file=sys.stderr)
        return 2

    records, parse_errors = _parse_jsonl(path)
    report = validate(records)
    report["errors"] = parse_errors + report["errors"]

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if args.quiet:
        print("FAIL" if report["errors"] else "OK")
    else:
        _print_report(report)

    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
