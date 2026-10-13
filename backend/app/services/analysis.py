"""Explainable, rule-based risk analysis.

IMPORTANT: This is a deterministic keyword/pattern baseline. It is deliberately
NOT a trained model, and ``legal-bert`` is not used anywhere. Every finding is
transparent: it records the rule that fired, why it matters and what to do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

from app.services.segmentation import Segment

MODEL_NAME = "rule-based-baseline-v1"

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
SEVERITY_WEIGHTS = {"LOW": 4, "MEDIUM": 10, "HIGH": 20, "CRITICAL": 35}


@dataclass(slots=True)
class Rule:
    code: str
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    citation: str | None
    patterns: tuple[Pattern[str], ...]
    exclude: tuple[Pattern[str], ...] = ()


def _c(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


RULES: tuple[Rule, ...] = (
    Rule(
        code="UNCAPPED_INDEMNITY",
        category="Indemnity",
        severity="CRITICAL",
        title="Uncapped indemnity obligation",
        description=(
            "An indemnity is given without a monetary cap or exclusion for "
            "consequential loss, which can expose the business to unlimited claims."
        ),
        recommendation=(
            "Insert a liability cap linked to fees paid in the preceding 12 months, "
            "exclude indirect losses and carve out the counterparty's own negligence."
        ),
        citation="Unfair Contract Terms Act 1977; standard market practice.",
        patterns=(_c(r"indemnif"), _c(r"hold\s+harmless")),
        exclude=(
            _c(r"(?:liabilit|indemnit)\w*\s+[^.]{0,30}\bcap(?:ped|s)?\b"),
            _c(r"\bcap(?:ped)?\s+(?:at|to)\b"),
            _c(r"maximum\s+(?:liability|amount|aggregate)"),
            _c(r"aggregate\s+liability"),
            _c(r"\blimited\s+to\b"),
            _c(r"shall\s+not\s+exceed"),
        ),
    ),
    Rule(
        code="UNLIMITED_LIABILITY",
        category="Limitation of Liability",
        severity="CRITICAL",
        title="Possibly unlimited liability",
        description=(
            "The wording suggests liability may be unlimited or expressly not "
            "excluded, removing the usual financial protection."
        ),
        recommendation="Introduce an aggregate liability cap and a clear exclusion of indirect losses.",
        citation="Standard limitation of liability drafting practice.",
        patterns=(
            _c(r"unlimited\s+liability"),
            _c(r"liability\s+shall\s+be\s+unlimited"),
            _c(r"no\s+limit\s+.{0,20}liabilit"),
            _c(r"shall\s+not\s+be\s+(limited|excluded)"),
        ),
    ),
    Rule(
        code="TERMINATION_FOR_CONVENIENCE",
        category="Termination",
        severity="HIGH",
        title="Termination for convenience",
        description=(
            "One party may terminate without cause, which can interrupt delivery "
            "and leave committed costs unrecovered."
        ),
        recommendation="Extend the notice period and add a wind-down or exit fee for committed costs.",
        citation="Standard commercial termination practice.",
        patterns=(
            _c(r"terminat\w*\s+.{0,30}(for\s+convenience|without\s+cause|at\s+any\s+time)"),
        ),
    ),
    Rule(
        code="SHORT_TERMINATION_NOTICE",
        category="Termination",
        severity="MEDIUM",
        title="Short notice period",
        description="A very short notice period limits the ability to plan for and manage the transition.",
        recommendation="Align the notice period with the delivery cycle, typically 30 to 60 days.",
        citation=None,
        patterns=(
            _c(r"(seven|seven \(7\)|\b7\b|five \(5\)|\b5\b|ten \(10\)|\b10\b|fourteen \(14\)|\b14\b)\s*days?.{0,25}notice"),
        ),
    ),
    Rule(
        code="EXTENDED_PAYMENT_TERMS",
        category="Payment Terms",
        severity="HIGH",
        title="Extended payment terms",
        description=(
            "A long payment window (60 days or more) negatively affects cash flow "
            "and working capital."
        ),
        recommendation="Reduce to 30 days and add interest for late payment where lawful.",
        citation="Late Payment of Commercial Debts (Interest) Act 1998.",
        patterns=(
            _c(r"(sixty \(60\)|\b60\b|ninety \(90\)|\b90\b|one hundred and twenty \(120\)|\b120\b)\s*days?.{0,20}(invoice|payment|receipt)"),
            _c(r"within\s+(60|90|120)\s+days"),
        ),
    ),
    Rule(
        code="BROAD_NON_COMPETE",
        category="Non-Compete",
        severity="HIGH",
        title="Broad non-compete restraint",
        description=(
            "A restrictive covenant may be wider in scope, duration or territory "
            "than is reasonably necessary to protect legitimate interests."
        ),
        recommendation="Narrow the restraint to named competitors, a defined client base and a shorter period.",
        citation="Restraint of trade doctrine; Tillman v Egon Zehnder (2019).",
        patterns=(_c(r"non-?compete"), _c(r"shall\s+not\s+.{0,20}compete"), _c(r"restraint\s+of\s+trade")),
    ),
    Rule(
        code="AUTO_RENEWAL",
        category="Term",
        severity="MEDIUM",
        title="Automatic renewal",
        description="The agreement renews automatically, which can create unintended long-term commitments.",
        recommendation="Add a clear opt-out window and a reminder before the renewal date.",
        citation=None,
        patterns=(_c(r"automatically\s+renew"), _c(r"auto-?renew"), _c(r"renew\w*\s+.{0,20}automatically")),
    ),
    Rule(
        code="UNILATERAL_AMENDMENT",
        category="General",
        severity="HIGH",
        title="Unilateral amendment right",
        description="One party may change material terms at its discretion without agreement.",
        recommendation="Require mutual written consent before any material amendment.",
        citation=None,
        patterns=(
            _c(r"(may|reserves\s+the\s+right\s+to)\s+(amend|modify|vary|change)\w*[^.]{0,40}(at\s+any\s+time|sole\s+discretion|from\s+time\s+to\s+time)"),
            _c(r"at\s+(its|their)\s+sole\s+discretion"),
        ),
    ),
    Rule(
        code="BROAD_IP_ASSIGNMENT",
        category="Intellectual Property",
        severity="MEDIUM",
        title="Broad intellectual property assignment",
        description="Intellectual property may be assigned more broadly than the engagement requires.",
        recommendation="Limit the assignment to IP created in the course of the engagement.",
        citation="Patents Act 1977 s.39 (employment context).",
        patterns=(
            _c(r"assign\w*\s+.{0,30}intellectual\s+property"),
            _c(r"intellectual\s+property\s+.{0,40}(vest|assign|belong)"),
        ),
    ),
    Rule(
        code="LIQUIDATED_DAMAGES",
        category="Remedies",
        severity="HIGH",
        title="Liquidated damages or penalty",
        description="Fixed financial remedies may be disproportionate and could be unenforceable.",
        recommendation="Confirm the sum is a genuine estimate of loss, not a penalty.",
        citation="Cavendish Square Holding v Talal El Makdessi (2015).",
        patterns=(_c(r"liquidated\s+damages"), _c(r"penalt(y|ies)"), _c(r"break\s+fee")),
    ),
    Rule(
        code="DATA_PROTECTION_GAP",
        category="Data Protection",
        severity="MEDIUM",
        title="Incomplete data protection terms",
        description=(
            "Personal data is referenced but mandatory processor terms "
            "(sub-processor consent, breach notification, assistance) are not clearly stated."
        ),
        recommendation="Append a data processing agreement containing the Article 28 mandatory terms.",
        citation="UK GDPR Article 28; Data Protection Act 2018.",
        patterns=(_c(r"personal\s+data"), _c(r"data\s+protection"), _c(r"\bgdpr\b")),
        exclude=(_c(r"article\s+28"), _c(r"sub-?processor"), _c(r"data\s+processing\s+agreement")),
    ),
    Rule(
        code="PERPETUAL_CONFIDENTIALITY",
        category="Confidentiality",
        severity="MEDIUM",
        title="Perpetual confidentiality obligation",
        description="Confidentiality duties survive indefinitely, which may be unreasonable for ordinary information.",
        recommendation="Limit confidentiality to a defined period, keeping trade secrets perpetual only.",
        citation=None,
        patterns=(_c(r"confidential[^.]{0,40}(perpetual|in\s+perpetuity|indefinitely)"),),
    ),
    Rule(
        code="FOREIGN_GOVERNING_LAW",
        category="Governing Law",
        severity="MEDIUM",
        title="Foreign governing law or forum",
        description="A foreign governing law or exclusive forum can increase dispute cost and uncertainty.",
        recommendation="Confirm the choice is acceptable; consider neutral arbitration or home jurisdiction.",
        citation=None,
        patterns=(
            _c(r"laws?\s+of\s+(?:\w+\s+){0,3}(germany|france|ireland|netherlands|singapore|delaware|new\s+york|california)"),
            _c(r"govern(?:ed|ing)\s+by\s+.{0,25}(german|french|irish|dutch|singapore|delaware|new\s+york|california)\s+law"),
            _c(r"courts?\s+of\s+(berlin|delaware|new\s+york|paris|singapore)"),
        ),
    ),
    Rule(
        code="EXCLUSIVITY",
        category="Exclusivity",
        severity="MEDIUM",
        title="Exclusivity commitment",
        description="An exclusivity obligation may restrict commercial flexibility.",
        recommendation="Confirm scope, duration and any minimum volumes or carve-outs.",
        citation=None,
        patterns=(_c(r"exclusiv"),),
    ),
    Rule(
        code="ARBITRATION",
        category="Dispute Resolution",
        severity="LOW",
        title="Arbitration clause",
        description="Disputes are resolved by arbitration. Review the seat, rules and cost allocation.",
        recommendation="Confirm the institution, seat and number of arbitrators are acceptable.",
        citation=None,
        patterns=(_c(r"arbitrat"),),
    ),
    Rule(
        code="CONFIDENTIALITY_STANDARD",
        category="Confidentiality",
        severity="LOW",
        title="Confidentiality obligation",
        description="Confidentiality obligations are present and should be reviewed for balance and carve-outs.",
        recommendation="Confirm mutual scope, permitted disclosures and the survival period.",
        citation=None,
        patterns=(_c(r"confidential\s+information"),),
    ),
    Rule(
        code="ASSIGNMENT_RESTRICTION",
        category="Assignment",
        severity="LOW",
        title="Assignment restriction",
        description="Assignment of the agreement is restricted, which may affect corporate transactions.",
        recommendation="Confirm the restriction allows assignment to affiliates or on a change of control.",
        citation=None,
        patterns=(_c(r"shall\s+not\s+assign"), _c(r"not\s+assign\s+this\s+agreement")),
    ),
    Rule(
        code="FORCE_MAJEURE",
        category="Force Majeure",
        severity="LOW",
        title="Force majeure provision",
        description="A force majeure clause is present. Review the covered events and notice requirements.",
        recommendation="Confirm the events covered and that notice and mitigation duties are reasonable.",
        citation=None,
        patterns=(_c(r"force\s+majeure"), _c(r"act\s+of\s+god")),
    ),
)


CLAUSE_TYPE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Indemnity", ("indemnif", "hold harmless")),
    ("Limitation of Liability", ("limitation of liability", "liabilit", "shall not be liable")),
    ("Termination", ("terminat", "expiry", "expiration")),
    ("Payment", ("payment", "invoice", "fees", "remuneration", "charges")),
    ("Confidentiality", ("confidential",)),
    ("Intellectual Property", ("intellectual property", "copyright", "patent", "trade mark", "trademark")),
    ("Governing Law", ("governing law", "governing laws", "governed by", "jurisdiction")),
    ("Data Protection", ("data protection", "personal data", "gdpr")),
    ("Non-Compete", ("non-compete", "non compete", "compete", "restraint of trade")),
    ("Force Majeure", ("force majeure", "act of god")),
    ("Assignment", ("assign",)),
    ("Warranty", ("warrant", "representation")),
    ("Dispute Resolution", ("arbitration", "dispute")),
)


@dataclass(slots=True)
class FindingDraft:
    segment_index: int
    rule_code: str
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    citation: str | None


@dataclass(slots=True)
class AnalysisResult:
    findings: list[FindingDraft] = field(default_factory=list)
    risk_score: float = 0.0
    summary: str = ""
    clause_type_by_index: dict[int, str] = field(default_factory=dict)
    risk_level_by_index: dict[int, str] = field(default_factory=dict)


def _infer_clause_type(text: str) -> str:
    lowered = text.lower()
    for clause_type, keywords in CLAUSE_TYPE_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return clause_type
    return "General"


def _highest_severity(severities: list[str]) -> str | None:
    if not severities:
        return None
    return max(severities, key=lambda severity: SEVERITY_ORDER.get(severity, 0))


def _score(findings: list[FindingDraft]) -> float:
    raw = sum(SEVERITY_WEIGHTS.get(finding.severity, 0) for finding in findings)
    return float(min(100, raw))


def _summary(findings: list[FindingDraft], clause_count: int, risk_score: float) -> str:
    counts = {level: 0 for level in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    band = "LOW"
    if risk_score >= 75:
        band = "CRITICAL"
    elif risk_score >= 50:
        band = "HIGH"
    elif risk_score >= 25:
        band = "MEDIUM"

    if not findings:
        return (
            f"Rule-based analysis reviewed {clause_count} clause(s) and detected no "
            f"risk indicators. Generated by {MODEL_NAME}; this is a deterministic "
            f"baseline and not a legal opinion."
        )

    return (
        f"Rule-based analysis reviewed {clause_count} clause(s) and detected "
        f"{len(findings)} risk indicator(s): {counts['CRITICAL']} critical, "
        f"{counts['HIGH']} high, {counts['MEDIUM']} medium, {counts['LOW']} low. "
        f"Overall risk {int(risk_score)}/100 ({band}). Generated by {MODEL_NAME} "
        f"(explainable rule-based baseline); no machine-learning model was used."
    )


def analyze_segments(segments: list[Segment]) -> AnalysisResult:
    """Run the rule set over each clause segment and aggregate the outcome."""

    findings: list[FindingDraft] = []
    clause_type_by_index: dict[int, str] = {}
    severities_by_index: dict[int, list[str]] = {}

    for index, segment in enumerate(segments):
        clause_type_by_index[index] = _infer_clause_type(segment.text)
        for rule in RULES:
            if any(pattern.search(segment.text) for pattern in rule.patterns):
                if rule.exclude and any(pattern.search(segment.text) for pattern in rule.exclude):
                    continue
                findings.append(
                    FindingDraft(
                        segment_index=index,
                        rule_code=rule.code,
                        category=rule.category,
                        severity=rule.severity,
                        title=rule.title,
                        description=rule.description,
                        recommendation=rule.recommendation,
                        citation=rule.citation,
                    )
                )
                severities_by_index.setdefault(index, []).append(rule.severity)

    risk_level_by_index: dict[int, str] = {}
    for index, severities in severities_by_index.items():
        highest = _highest_severity(severities)
        if highest is not None:
            risk_level_by_index[index] = highest

    risk_score = _score(findings)
    return AnalysisResult(
        findings=findings,
        risk_score=risk_score,
        summary=_summary(findings, len(segments), risk_score),
        clause_type_by_index=clause_type_by_index,
        risk_level_by_index=risk_level_by_index,
    )


__all__ = [
    "AnalysisResult",
    "CLAUSE_TYPE_KEYWORDS",
    "FindingDraft",
    "MODEL_NAME",
    "RULES",
    "SEVERITY_ORDER",
    "analyze_segments",
]
