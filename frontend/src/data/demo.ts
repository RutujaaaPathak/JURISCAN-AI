import { RISK_LEVELS, riskLevelFromScore } from "@/lib/risk"
import type { RiskLevel } from "@/lib/risk"

/**
 * DEMO DATA ONLY.
 *
 * Everything in this module is illustrative sample data used to preview the
 * interface. It is NOT produced by a trained model and must never be presented
 * to users as a real analysis result. Pages that render this data display a
 * visible "Demo data" notice. Real analysis output will come from the backend
 * in a later phase.
 */

export type DocumentStatus = "analyzed" | "review" | "processing" | "queued"

export interface ClauseFinding {
  id: string
  category: string
  clauseRef: string
  severity: RiskLevel
  confidence: number
  text: string
  explanation: string
  recommendation: string
  citations: string[]
}

export interface DocumentRecord {
  id: string
  title: string
  fileName: string
  docType: string
  jurisdiction: string
  sizeLabel: string
  pages: number
  words: number
  status: DocumentStatus
  riskScore: number
  uploadedAt: string
  analyzedAt: string | null
  owner: string
  counterparty: string
  findings: ClauseFinding[]
}

export const DEMO_DATA_NOTICE =
  "Sample data for interface preview. Not produced by a trained model and not a real analysis result."

export const documents: DocumentRecord[] = [
  {
    id: "DOC-1042",
    title: "Master Services Agreement — Northwind Ltd.",
    fileName: "northwind-msa-2026.pdf",
    docType: "Services",
    jurisdiction: "England & Wales",
    sizeLabel: "482 KB",
    pages: 24,
    words: 9180,
    status: "analyzed",
    riskScore: 78,
    uploadedAt: "2026-10-06T09:14:00Z",
    analyzedAt: "2026-10-06T09:17:00Z",
    owner: "Priya Raman",
    counterparty: "Northwind Ltd.",
    findings: [
      {
        id: "F-1042-1",
        category: "Indemnity",
        clauseRef: "Clause 11.2",
        severity: "critical",
        confidence: 0.94,
        text: "The Supplier shall indemnify, defend and hold harmless the Customer and its affiliates against any and all losses, claims, damages, liabilities and expenses of whatsoever nature, howsoever arising, whether or not foreseeable.",
        explanation:
          "Uncapped and unrestricted indemnity favouring the counterparty. No monetary cap, no exclusion for consequential loss, and no carve-out for the Supplier's own negligence.",
        recommendation:
          "Insert a liability cap tied to fees paid in the preceding 12 months and exclude indirect or consequential losses.",
        citations: ["Contractual indemnities — Unfair Contract Terms Act 1977", "Rose v. Boris (2022) EWHC 143"],
      },
      {
        id: "F-1042-2",
        category: "Termination",
        clauseRef: "Clause 8.4",
        severity: "high",
        confidence: 0.88,
        text: "The Customer may terminate this Agreement for convenience on seven (7) days' written notice without liability for any charges accrued after the effective date of termination.",
        explanation:
          "A very short termination-for-convenience window with no exit fee or wind-down payment exposes the Supplier to unrecovered mobilisation costs.",
        recommendation: "Extend the notice period to 60 days and add a wind-down fee for committed costs.",
        citations: ["Termination for convenience — common law principles"],
      },
      {
        id: "F-1042-3",
        category: "Governing Law",
        clauseRef: "Clause 18.1",
        severity: "medium",
        confidence: 0.81,
        text: "This Agreement shall be governed by and construed in accordance with the laws of England and Wales and the parties submit to the exclusive jurisdiction of the courts of England and Wales.",
        explanation:
          "Governing law is acceptable, but exclusive jurisdiction may complicate enforcement where assets are held offshore.",
        recommendation: "Confirm matching governing law across all schedules and related order forms.",
        citations: ["Jurisdiction clauses — Brussels I Recast (background)"],
      },
      {
        id: "F-1042-4",
        category: "Confidentiality",
        clauseRef: "Clause 12.3",
        severity: "low",
        confidence: 0.76,
        text: "Each party shall keep the other's Confidential Information confidential for a period of three (3) years following termination of this Agreement.",
        explanation: "Standard mutual confidentiality with a defined survival period and reasonable carve-outs.",
        recommendation: "No change required; confirm trade-secret survival is perpetual where applicable.",
        citations: ["Trade secrets — TRIPS Art. 39"],
      },
      {
        id: "F-1042-5",
        category: "Payment Terms",
        clauseRef: "Clause 6.2",
        severity: "high",
        confidence: 0.9,
        text: "Payment shall be due within one hundred and twenty (120) days of the date of a valid invoice.",
        explanation:
          "A 120-day payment window significantly exceeds market norms and materially affects cash flow and working capital.",
        recommendation: "Reduce to 30 days (or 45 days maximum) and add interest on late payment.",
        citations: ["Late Payment of Commercial Debts (Interest) Act 1998"],
      },
      {
        id: "F-1042-6",
        category: "Data Protection",
        clauseRef: "Clause 15.1",
        severity: "medium",
        confidence: 0.79,
        text: "Each party shall comply with all applicable data protection legislation. The Customer may audit the Supplier's processing activities on reasonable notice.",
        explanation:
          "Data protection obligations are high-level and omit required processor terms such as sub-processor consent and breach notification timelines.",
        recommendation: "Append a data processing agreement with the Article 28 mandatory terms.",
        citations: ["UK GDPR Art. 28", "Data Protection Act 2018"],
      },
    ],
  },
  {
    id: "DOC-1041",
    title: "Mutual Non-Disclosure Agreement — Acme Corp",
    fileName: "acme-mnda.pdf",
    docType: "NDA",
    jurisdiction: "Delaware, USA",
    sizeLabel: "96 KB",
    pages: 6,
    words: 2100,
    status: "analyzed",
    riskScore: 22,
    uploadedAt: "2026-10-05T14:02:00Z",
    analyzedAt: "2026-10-05T14:03:00Z",
    owner: "Priya Raman",
    counterparty: "Acme Corp",
    findings: [
      {
        id: "F-1041-1",
        category: "Confidentiality",
        clauseRef: "Clause 3",
        severity: "low",
        confidence: 0.92,
        text: "The Receiving Party shall protect the Disclosing Party's Confidential Information using at least a reasonable degree of care.",
        explanation: "Mutual obligations with a reasonable standard of care and standard exclusions.",
        recommendation: "No change required.",
        citations: ["Defend Trade Secrets Act 2016"],
      },
      {
        id: "F-1041-2",
        category: "Term",
        clauseRef: "Clause 7",
        severity: "low",
        confidence: 0.85,
        text: "This Agreement shall remain in effect for two (2) years from the Effective Date.",
        explanation: "A two-year term is within common market ranges for mutual NDAs.",
        recommendation: "No change required.",
        citations: [],
      },
    ],
  },
  {
    id: "DOC-1039",
    title: "Commercial Lease — 145 Bishopsgate",
    fileName: "bishopsgate-lease.pdf",
    docType: "Lease",
    jurisdiction: "England & Wales",
    sizeLabel: "1.2 MB",
    pages: 58,
    words: 21400,
    status: "review",
    riskScore: 64,
    uploadedAt: "2026-10-04T11:30:00Z",
    analyzedAt: "2026-10-04T11:36:00Z",
    owner: "Daniel Okafor",
    counterparty: "Bishopsgate Estates",
    findings: [
      {
        id: "F-1039-1",
        category: "Repair",
        clauseRef: "Clause 5.1",
        severity: "high",
        confidence: 0.89,
        text: "The Tenant shall keep the Premises in good and substantial repair and condition, including the replacement of all worn or damaged items.",
        explanation:
          "Full repairing obligation with no schedule of condition means the Tenant may inherit pre-existing disrepair.",
        recommendation: "Attach a photographic schedule of condition and limit the obligation accordingly.",
        citations: ["Repairing covenants — common law"],
      },
      {
        id: "F-1039-2",
        category: "Rent Review",
        clauseRef: "Clause 4.3",
        severity: "medium",
        confidence: 0.8,
        text: "The rent shall be reviewed every five years to the higher of open market rent or the rent payable immediately prior to review.",
        explanation: "Upward-only rent review lacks a downward adjustment mechanism.",
        recommendation: "Negotiate an open-market review without the upward-only restriction.",
        citations: [],
      },
      {
        id: "F-1039-3",
        category: "Break Clause",
        clauseRef: "Clause 9",
        severity: "critical",
        confidence: 0.93,
        text: "The Tenant's break right is conditional upon the Tenant having paid all rent and having performed all covenants up to the break date.",
        explanation:
          "Strict compliance conditions make the break right easy to forfeit; a minor breach can void the break entirely.",
        recommendation: "Reduce conditions to payment of rent only, exclusive of minor breaches.",
        citations: ["Break options — strict compliance principle"],
      },
    ],
  },
  {
    id: "DOC-1038",
    title: "Employment Contract — Senior Engineer",
    fileName: "employment-senior-engineer.docx",
    docType: "Employment",
    jurisdiction: "England & Wales",
    sizeLabel: "140 KB",
    pages: 12,
    words: 5400,
    status: "analyzed",
    riskScore: 41,
    uploadedAt: "2026-10-03T08:45:00Z",
    analyzedAt: "2026-10-03T08:47:00Z",
    owner: "Sofia Marchetti",
    counterparty: "Internal",
    findings: [
      {
        id: "F-1038-1",
        category: "Non-Compete",
        clauseRef: "Clause 14",
        severity: "high",
        confidence: 0.87,
        text: "For a period of twelve (12) months following termination the Employee shall not engage in any competing business within any territory in which the Company operates.",
        explanation:
          "Worldwide-style restraint for 12 months is likely broader than necessary to protect legitimate business interests.",
        recommendation: "Narrow to named competitors, a defined client base and a shorter 6-month period.",
        citations: ["Restraint of trade — Tillman v. Egon Zehnder (2019)"],
      },
      {
        id: "F-1038-2",
        category: "Intellectual Property",
        clauseRef: "Clause 11",
        severity: "medium",
        confidence: 0.83,
        text: "All intellectual property created by the Employee during employment shall vest absolutely in the Company.",
        explanation: "Assignment covers work created outside role scope without an exception.",
        recommendation: "Limit the assignment to IP created in the course of employment duties.",
        citations: ["Patents Act 1977 s.39"],
      },
    ],
  },
  {
    id: "DOC-1036",
    title: "Software Licence Agreement — Vertex GmbH",
    fileName: "vertex-licence.pdf",
    docType: "Licence",
    jurisdiction: "Germany",
    sizeLabel: "310 KB",
    pages: 18,
    words: 7300,
    status: "analyzed",
    riskScore: 55,
    uploadedAt: "2026-10-01T16:20:00Z",
    analyzedAt: "2026-10-01T16:24:00Z",
    owner: "Daniel Okafor",
    counterparty: "Vertex GmbH",
    findings: [
      {
        id: "F-1036-1",
        category: "Warranty",
        clauseRef: "Clause 7",
        severity: "medium",
        confidence: 0.82,
        text: "The Supplier warrants that the Software will perform substantially in accordance with the Documentation for ninety (90) days from delivery.",
        explanation: "Warranty period is on the short side for enterprise software.",
        recommendation: "Extend warranty to 12 months and add a service-level remedy.",
        citations: [],
      },
      {
        id: "F-1036-2",
        category: "Governing Law",
        clauseRef: "Clause 21",
        severity: "high",
        confidence: 0.85,
        text: "This Agreement is governed by German law and disputes shall be resolved in the courts of Berlin.",
        explanation: "Foreign governing law and venue add cost and uncertainty for a UK-based buyer.",
        recommendation: "Negotiate neutral arbitration or the buyer's home jurisdiction.",
        citations: [],
      },
    ],
  },
  {
    id: "DOC-1035",
    title: "Data Processing Agreement — CloudHost",
    fileName: "cloudhost-dpa.pdf",
    docType: "Policy",
    jurisdiction: "Ireland",
    sizeLabel: "204 KB",
    pages: 14,
    words: 4900,
    status: "processing",
    riskScore: 0,
    uploadedAt: "2026-10-07T07:05:00Z",
    analyzedAt: null,
    owner: "Sofia Marchetti",
    counterparty: "CloudHost",
    findings: [],
  },
  {
    id: "DOC-1033",
    title: "Supplier Terms & Conditions — Global Parts",
    fileName: "globalparts-terms.txt",
    docType: "Terms",
    jurisdiction: "England & Wales",
    sizeLabel: "42 KB",
    pages: 9,
    words: 3600,
    status: "queued",
    riskScore: 0,
    uploadedAt: "2026-10-07T06:58:00Z",
    analyzedAt: null,
    owner: "Priya Raman",
    counterparty: "Global Parts Ltd.",
    findings: [],
  },
]

export const documentTypes = Array.from(new Set(documents.map((doc) => doc.docType))).sort()

export function getDocumentById(id: string): DocumentRecord | undefined {
  return documents.find((doc) => doc.id === id)
}

export function documentRiskLevel(doc: DocumentRecord): RiskLevel {
  return riskLevelFromScore(doc.riskScore)
}

export function riskDistribution(docs: DocumentRecord[] = documents): Record<RiskLevel, number> {
  const counts: Record<RiskLevel, number> = { low: 0, medium: 0, high: 0, critical: 0 }
  for (const doc of docs) {
    if (doc.status !== "analyzed" && doc.status !== "review") continue
    counts[documentRiskLevel(doc)] += 1
  }
  return counts
}

export function allFindings(docs: DocumentRecord[] = documents): ClauseFinding[] {
  return docs.flatMap((doc) => doc.findings)
}

export function severityCounts(docs: DocumentRecord[] = documents): Record<RiskLevel, number> {
  const counts: Record<RiskLevel, number> = { low: 0, medium: 0, high: 0, critical: 0 }
  for (const finding of allFindings(docs)) {
    counts[finding.severity] += 1
  }
  return counts
}

export function categoryCounts(docs: DocumentRecord[] = documents): { category: string; count: number }[] {
  const map = new Map<string, number>()
  for (const finding of allFindings(docs)) {
    map.set(finding.category, (map.get(finding.category) ?? 0) + 1)
  }
  return Array.from(map.entries())
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)
}

export function overallStats(docs: DocumentRecord[] = documents) {
  const analyzed = docs.filter((doc) => doc.status === "analyzed" || doc.status === "review")
  const avgRisk =
    analyzed.length > 0
      ? Math.round(analyzed.reduce((sum, doc) => sum + doc.riskScore, 0) / analyzed.length)
      : 0
  const highRiskFindings = allFindings(docs).filter(
    (finding) => finding.severity === "high" || finding.severity === "critical",
  ).length
  const pendingReview = docs.filter((doc) => doc.status === "review").length
  const inPipeline = docs.filter((doc) => doc.status === "processing" || doc.status === "queued").length
  return {
    totalDocuments: docs.length,
    analyzed: analyzed.length,
    avgRisk,
    highRiskFindings,
    pendingReview,
    inPipeline,
  }
}

export const uploadTrend = [
  { label: "Mon", value: 4 },
  { label: "Tue", value: 6 },
  { label: "Wed", value: 3 },
  { label: "Thu", value: 8 },
  { label: "Fri", value: 5 },
  { label: "Sat", value: 2 },
  { label: "Sun", value: 1 },
]

export const severityOrder = RISK_LEVELS
