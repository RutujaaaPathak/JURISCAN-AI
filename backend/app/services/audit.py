"""Serialization helpers for company audit reports.

An audit report is the latest analysis of a company document. There is no
separate report table, so the status is always derived from persisted analysis
and document state and can never claim a report exists when it does not.
"""

from __future__ import annotations

from datetime import datetime

from app.models import Analysis, Clause, Document, RiskFinding


def risk_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def safety_score(score: float | None) -> float | None:
    if score is None:
        return None
    return round(max(0.0, min(100.0, 100.0 - score)), 1)


def latest_analysis(document: Document) -> Analysis | None:
    if not document.analyses:
        return None
    return max(document.analyses, key=lambda analysis: (analysis.created_at, analysis.id))


def report_status(document: Document, analysis: Analysis | None) -> str:
    if analysis is not None:
        if analysis.status == "COMPLETED":
            return "READY"
        if analysis.status == "FAILED":
            return "FAILED"
        if analysis.status in ("PENDING", "RUNNING"):
            return "PENDING"
    if document.status == "FAILED":
        return "FAILED"
    if document.status in ("PENDING", "PROCESSING"):
        return "PENDING"
    return "NOT_GENERATED"


def audit_date(document: Document, analysis: Analysis | None) -> datetime | None:
    if analysis is not None:
        return analysis.completed_at or analysis.started_at or analysis.created_at
    return document.extracted_at or document.created_at


def _finding_payload(finding: RiskFinding, clause: Clause | None) -> dict:
    return {
        "id": finding.id,
        "analysis_id": finding.analysis_id,
        "clause_id": finding.clause_id,
        "rule_code": finding.rule_code,
        "severity": finding.severity,
        "title": finding.title,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "citation": finding.citation,
        "clause_number": clause.clause_number if clause else None,
        "clause_heading": clause.heading if clause else None,
        "clause_page": clause.page_number if clause else None,
        "clause_label": clause.label if clause else None,
        "clause_level": clause.level if clause else None,
        "created_at": finding.created_at,
        "updated_at": finding.updated_at,
    }


def summary_payload(document: Document) -> dict:
    analysis = latest_analysis(document)
    findings = analysis.risk_findings if analysis else []
    score = analysis.risk_score if analysis else None
    return {
        "document_id": document.id,
        "document_title": document.title,
        "filename": document.filename,
        "file_type": document.file_type,
        "analysis_id": analysis.id if analysis else None,
        "model_name": analysis.model_name if analysis else None,
        "analysis_status": analysis.status if analysis else None,
        "report_status": report_status(document, analysis),
        "audit_date": audit_date(document, analysis),
        "risk_score": score,
        "risk_level": risk_band(score),
        "safety_score": safety_score(score),
        "finding_count": len(findings),
        "high_risk_count": sum(
            1 for finding in findings if finding.severity in ("HIGH", "CRITICAL")
        ),
        "error_message": document.error_message
        or (analysis.error_message if analysis else None),
    }


def detail_payload(document: Document) -> dict:
    analysis = latest_analysis(document)
    clauses = sorted(document.clauses, key=lambda clause: clause.clause_number)
    clauses_by_id = {clause.id: clause for clause in clauses}
    payload = summary_payload(document)
    payload.update(
        {
            "analysis_summary": analysis.summary if analysis else None,
            "clause_count": len(clauses),
            "findings": (
                [
                    _finding_payload(finding, clauses_by_id.get(finding.clause_id or -1))
                    for finding in analysis.risk_findings
                ]
                if analysis
                else []
            ),
        }
    )
    return payload


__all__ = [
    "audit_date",
    "detail_payload",
    "latest_analysis",
    "report_status",
    "risk_band",
    "safety_score",
    "summary_payload",
]
