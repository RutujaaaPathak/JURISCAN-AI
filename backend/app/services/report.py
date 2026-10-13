"""Server-side PDF generation for the contract analysis report.

Builds a real, text-selectable PDF with pymupdf (already a runtime dependency
used by the OCR service). Every value comes from the persisted analysis and
clause data; nothing is hardcoded or fabricated.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pymupdf

from app.models import Analysis, Clause, Document, RiskFinding
from app.services.analysis import MODEL_NAME, SEVERITY_ORDER

PAGE_W = 595.28
PAGE_H = 841.89
MARGIN = 48.0
TOP = 70.0
BOTTOM = 52.0
BODY_LEFT = MARGIN
BODY_RIGHT = PAGE_W - MARGIN
BODY_WIDTH = BODY_RIGHT - BODY_LEFT
BODY_BOTTOM = PAGE_H - BOTTOM

FONT = "helv"
FONT_BOLD = "hebo"

DARK = (0.11, 0.12, 0.16)
MUTED = (0.42, 0.45, 0.50)
ACCENT = (0.18, 0.24, 0.62)

SEVERITY_COLOR = {
    "LOW": (0.06, 0.73, 0.51),
    "MEDIUM": (0.96, 0.62, 0.04),
    "HIGH": (0.98, 0.45, 0.09),
    "CRITICAL": (0.86, 0.15, 0.15),
}

_ASCII_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2011": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
)


def _printable(text: str) -> str:
    """Make text safe for the base-14 Helvetica (WinAnsi) encoding.

    Only presentation characters are substituted; the wording is preserved.
    Characters outside WinAnsi are replaced with "?" so text can never abort
    rendering.
    """

    cleaned = text.translate(_ASCII_MAP)
    return "".join(char if ord(char) < 256 else "?" for char in cleaned)


def _band(score: float | None) -> str:
    if score is None:
        return "LOW"
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def _join_names(names: list[str]) -> str:
    unique: list[str] = []
    for name in names:
        if name and name not in unique:
            unique.append(name)
    if len(unique) <= 1:
        return unique[0] if unique else "the flagged clause(s)"
    return ", ".join(unique[:-1]) + f" and {unique[-1]}"


def executive_summary(findings: list[RiskFinding], clause_count: int) -> list[str]:
    """Plain-English summary paragraphs derived from the actual findings."""

    if not findings:
        return [
            f"This automated screen looked across {clause_count} clause(s) and found "
            "nothing to flag.",
            "That does not mean the contract is legally safe - it means none of the "
            "risk patterns this tool checks for were detected.",
            "A lawyer should still review the contract before you sign.",
        ]

    counts = {level: 0 for level in SEVERITY_ORDER}
    critical: list[str] = []
    high: list[str] = []
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
        if finding.severity == "CRITICAL":
            critical.append(finding.title)
        elif finding.severity == "HIGH":
            high.append(finding.title)

    paragraphs = [
        "The automated screen reviewed "
        f"{clause_count} clause(s) and flagged {len(findings)} point(s) to check - "
        f"{counts['CRITICAL']} critical, {counts['HIGH']} high, "
        f"{counts['MEDIUM']} medium and {counts['LOW']} low.",
    ]

    focus = critical + high
    if focus:
        paragraphs.append(
            "The main areas to look at are " + _join_names(focus[:4]) + "."
        )
    else:
        paragraphs.append(
            "The points raised are low-to-medium priority, but still worth reading."
        )

    paragraphs.append(
        "Flagged wording may shift risk, cost or flexibility in ways worth "
        "understanding before you sign."
    )
    paragraphs.append(
        "This tool detects phrasing patterns. It does not judge whether a clause is "
        "lawful. Review the flagged points with a lawyer before signing."
    )
    return paragraphs


def severity_impact(severity: str) -> str:
    impact = {
        "CRITICAL": (
            "Can create large, open-ended financial or legal exposure. Treat this as "
            "a must-review before signing."
        ),
        "HIGH": (
            "May shift material risk or cost onto you. Worth negotiating before signing."
        ),
        "MEDIUM": (
            "May add obligations or inconvenience over time. Clarify the wording."
        ),
        "LOW": (
            "Usually routine, but confirm the wording is fair and balanced."
        ),
    }
    return impact.get(severity, impact["LOW"])


def _fit(text: str, fontsize: float, max_width: float) -> str:
    while text and pymupdf.get_text_length(text, fontname=FONT, fontsize=fontsize) > max_width:
        text = text[:-1]
    return text


class _Writer:
    def __init__(self, document: pymupdf.Document) -> None:
        self.doc = document
        self.page = document.new_page()
        self.y = TOP

    def _new_page(self) -> None:
        self.page = self.doc.new_page()
        self.y = TOP
        self._footer(len(self.doc))

    def _footer(self, page_number: int) -> None:
        baseline = PAGE_H - 24
        self.page.insert_text(
            (MARGIN, baseline),
            "JURISCAN-AI - automated preliminary review",
            fontsize=7,
            fontname=FONT,
            color=MUTED,
        )
        self.page.insert_text(
            (BODY_RIGHT - 30, baseline),
            str(page_number),
            fontsize=7,
            fontname=FONT,
            color=MUTED,
        )

    def _ensure(self, height: float) -> None:
        if self.y + height > BODY_BOTTOM:
            self._new_page()

    def _wrap(self, text: str, fontsize: float, max_width: float) -> list[str]:
        words = _printable(text).split()
        lines: list[str] = []
        current: list[str] = []
        current_width = 0.0
        for word in words:
            word_width = pymupdf.get_text_length(
                f"{word} ", fontname=FONT, fontsize=fontsize
            )
            if current and current_width + word_width > max_width:
                lines.append(" ".join(current))
                current = [word]
                current_width = word_width
            else:
                current.append(word)
                current_width += word_width
        if current:
            lines.append(" ".join(current))
        return lines

    def heading(self, text: str, size: float = 13.0, color: tuple = DARK, spacing_after: float = 6.0) -> None:
        line_height = size * 1.35
        self._ensure(line_height + spacing_after)
        self.page.insert_text(
            (BODY_LEFT, self.y + size),
            _printable(text),
            fontsize=size,
            fontname=FONT_BOLD,
            color=color,
        )
        self.y += line_height + spacing_after

    def para(
        self,
        text: str,
        size: float = 9.0,
        color: tuple = DARK,
        spacing_after: float = 5.0,
    ) -> None:
        lines = self._wrap(text, size, BODY_WIDTH)
        line_height = size * 1.32
        self._ensure(len(lines) * line_height + spacing_after)
        for line in lines:
            self.page.insert_text(
                (BODY_LEFT, self.y + size),
                _printable(line),
                fontsize=size,
                fontname=FONT,
                color=color,
            )
            self.y += line_height
        self.y += spacing_after

    def kv(self, label: str, value: str) -> None:
        self._ensure(14)
        self.page.insert_text(
            (BODY_LEFT, self.y + 9),
            _printable(label),
            fontsize=9,
            fontname=FONT_BOLD,
            color=MUTED,
        )
        self.page.insert_text(
            (BODY_LEFT + 118, self.y + 9),
            _printable(_fit(value, 9, BODY_WIDTH - 118)),
            fontsize=9,
            fontname=FONT,
            color=DARK,
        )
        self.y += 14

    def rule(self, width: float = BODY_WIDTH) -> None:
        self._ensure(8)
        self.page.draw_line(
            (BODY_LEFT, self.y),
            (BODY_LEFT + width, self.y),
            color=(0.82, 0.84, 0.88),
            width=0.7,
        )
        self.y += 8

    def bar(self, fraction: float, color: tuple, left_label: str, right_label: str) -> None:
        bar_height = 12.0
        self._ensure(bar_height + 22)
        top = self.y
        self.page.draw_rect(
            pymupdf.Rect(BODY_LEFT, top, BODY_RIGHT, top + bar_height),
            color=None,
            fill=(0.92, 0.93, 0.95),
        )
        fill_width = max(0.0, min(1.0, fraction)) * BODY_WIDTH
        if fill_width > 0:
            self.page.draw_rect(
                pymupdf.Rect(BODY_LEFT, top, BODY_LEFT + fill_width, top + bar_height),
                color=None,
                fill=color,
            )
        self.page.insert_text(
            (BODY_LEFT, top + bar_height + 11),
            _printable(left_label),
            fontsize=8,
            fontname=FONT_BOLD,
            color=DARK,
        )
        self.page.insert_text(
            (BODY_RIGHT - 60, top + bar_height + 11),
            _printable(_fit(right_label, 8, 60)),
            fontsize=8,
            fontname=FONT,
            color=MUTED,
        )
        self.y = top + bar_height + 16

    def finding_block(self, finding: RiskFinding, clause: Clause | None) -> None:
        severity = finding.severity
        color = SEVERITY_COLOR.get(severity, SEVERITY_COLOR["LOW"])

        clause_ref_parts: list[str] = []
        if clause is not None and clause.clause_number is not None:
            clause_ref_parts.append(f"Clause {clause.clause_number}")
        if clause is not None and clause.page_number is not None:
            clause_ref_parts.append(f"p.{clause.page_number}")
        ref = " - ".join(clause_ref_parts)
        ref_width = (
            pymupdf.get_text_length(_printable(ref), fontname=FONT, fontsize=8)
            if ref
            else 0
        )

        self._ensure(16)
        severity_word = severity
        severity_width = pymupdf.get_text_length(
            _printable(severity_word), fontname=FONT_BOLD, fontsize=9.5
        )
        title_width = BODY_WIDTH - severity_width - 6 - (ref_width + 2 if ref else 0)
        self.page.insert_text(
            (BODY_LEFT, self.y + 10),
            _printable(severity_word),
            fontsize=9.5,
            fontname=FONT_BOLD,
            color=color,
        )
        self.page.insert_text(
            (BODY_LEFT + severity_width + 6, self.y + 10),
            _printable(_fit(finding.title, 9.5, title_width)),
            fontsize=9.5,
            fontname=FONT,
            color=DARK,
        )
        if ref:
            self.page.insert_text(
                (BODY_RIGHT - ref_width - 2, self.y + 9),
                _printable(ref),
                fontsize=8,
                fontname=FONT,
                color=MUTED,
            )
        self.y += 16

        clause_text = clause.text if clause is not None else None
        if clause_text:
            self.para(
                _printable(clause_text),
                size=8.5,
                color=(0.15, 0.17, 0.22),
                spacing_after=3,
            )
        else:
            self.para(
                "Original contract wording: not available in the extracted document.",
                size=8.5,
                color=MUTED,
                spacing_after=3,
            )

        for sub_label, sub_value in (
            ("Why it was flagged", finding.description),
            ("What it could mean for you", severity_impact(severity)),
            (
                "Suggested next step",
                finding.recommendation
                or "Review this clause with a legal professional before signing.",
            ),
        ):
            sub_title = sub_label + ": "
            title_width = pymupdf.get_text_length(
                _printable(sub_title), fontname=FONT_BOLD, fontsize=8.5
            )
            body_lines = self._wrap(sub_value, 8.5, BODY_WIDTH - title_width)
            line_height = 8.5 * 1.32
            self._ensure(len(body_lines) * line_height + 3)
            first = True
            for body_line in body_lines:
                if first:
                    self.page.insert_text(
                        (BODY_LEFT, self.y + 8.5),
                        _printable(sub_title),
                        fontsize=8.5,
                        fontname=FONT_BOLD,
                        color=MUTED,
                    )
                    self.page.insert_text(
                        (BODY_LEFT + title_width, self.y + 8.5),
                        _printable(body_line),
                        fontsize=8.5,
                        fontname=FONT,
                        color=DARK,
                    )
                else:
                    self.page.insert_text(
                        (BODY_LEFT + title_width, self.y + 8.5),
                        _printable(body_line),
                        fontsize=8.5,
                        fontname=FONT,
                        color=DARK,
                    )
                self.y += line_height
                first = False
            self.y += 3
        self.rule()
        self.y += 6


def build_report_pdf(
    document: Document,
    analysis: Analysis,
    clauses_by_id: dict[int, Clause],
) -> bytes:
    """Render a complete analysis report for one document to PDF bytes."""

    raw = pymupdf.open()
    writer = _Writer(raw)

    findings = sorted(
        list(analysis.risk_findings),
        key=lambda finding: SEVERITY_ORDER.get(finding.severity, 0),
        reverse=True,
    )
    risk_score = analysis.risk_score or 0.0
    safety_score = round(max(0.0, min(100.0, 100.0 - risk_score)), 1)
    band = _band(analysis.risk_score)

    writer.page.insert_text(
        (BODY_LEFT, 40),
        "JURISCAN-AI",
        fontsize=14,
        fontname=FONT_BOLD,
        color=ACCENT,
    )
    report_title = "Contract Risk Analysis Report"
    writer.page.insert_text(
        (BODY_RIGHT - pymupdf.get_text_length(report_title, fontname=FONT, fontsize=9.5), 42),
        report_title,
        fontsize=9.5,
        fontname=FONT,
        color=MUTED,
    )
    writer.rule()

    writer.heading("Document", size=11.5)
    writer.kv("Filename", document.filename or document.title)
    writer.kv("Title", document.title)
    completed = analysis.completed_at or analysis.created_at or datetime.now(timezone.utc)
    writer.kv("Analyzed", completed.strftime("%Y-%m-%d %H:%M UTC"))
    writer.kv("Engine", analysis.model_name or MODEL_NAME)
    writer.rule()

    writer.heading("Overall assessment", size=11.5)
    counts_text = ", ".join(
        f"{sum(1 for f in findings if f.severity == level)} {level.lower()}"
        for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    )
    writer.para(
        f"{int(risk_score)}/100 risk score, {band} risk level. Legal safety score "
        f"{safety_score}/100 (higher means lower detected risk). {len(findings)} "
        f"finding(s): {counts_text}."
    )
    writer.bar(
        safety_score / 100.0,
        SEVERITY_COLOR.get(band, SEVERITY_COLOR["LOW"]),
        f"Legal safety {safety_score}/100",
        f"{band} risk level",
    )
    writer.rule()

    writer.heading("What this means for you", size=11.5)
    for paragraph in executive_summary(findings, len(document.clauses)):
        writer.para(paragraph)
    writer.rule()

    if findings:
        writer.heading("Issues to review", size=11.5)
    for finding in findings:
        clause = (
            clauses_by_id.get(finding.clause_id) if finding.clause_id is not None else None
        )
        writer.finding_block(finding, clause)

    writer.heading("How the score is calculated", size=11.5)
    writer.para(
        "Each finding is based on an explainable pattern rule and carries a severity "
        "weight (LOW 4, MEDIUM 10, HIGH 20, CRITICAL 35). The risk score is the sum "
        "of those weights, capped at 100. The legal safety score is the inverse "
        "(100 minus the risk score, floored at 0), so a higher safety score means "
        "fewer or less severe risk indicators."
    )
    writer.para(
        f"Generated by {MODEL_NAME}, a deterministic rule-based baseline. No "
        "machine-learning model (such as Legal-BERT) is used."
    )

    writer.heading("Limitations", size=11.5)
    writer.para(
        "This is an automated preliminary review. It detects phrasing patterns and "
        "can miss issues, and it does not judge whether a clause is lawful or "
        "enforceable. Exact clause wording is reproduced only where the active, "
        "segmented clause text was available."
    )

    writer._ensure(14)
    writer.page.insert_text(
        (BODY_LEFT, writer.y + 11),
        "Automated preliminary review. This report is not a legal opinion and does "
        "not guarantee enforceability.",
        fontsize=8,
        fontname=FONT_BOLD,
        color=(0.5, 0.16, 0.16),
    )

    return writer.doc.tobytes()


__all__ = ["build_report_pdf", "executive_summary", "severity_impact"]