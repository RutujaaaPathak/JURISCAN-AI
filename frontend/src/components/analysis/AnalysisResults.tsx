import { Download, FileText, Loader2, SearchCheck } from "lucide-react"
import { useCallback, useMemo, useState } from "react"

import { RiskScore } from "@/components/analysis/RiskScore"
import { SeverityBadge, StatusBadge } from "@/components/analysis/RiskBadges"
import { EmptyState } from "@/components/common/States"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { useToast } from "@/components/ui/toast"
import { ApiError } from "@/lib/api"
import { downloadAnalysisReport, downloadBlob } from "@/lib/documents"
import {
  executiveSummary,
  findingClauseRef,
  findingsBySeverity,
  severityImpactText,
} from "@/lib/executiveSummary"
import { formatDateTime, formatFileType } from "@/lib/format"
import { RISK_LEVELS, RISK_META, riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"
import type { DocumentDetail } from "@/lib/types"

export function AnalysisResults({
  doc,
  onAnalyzeAnother,
}: {
  doc: DocumentDetail
  onAnalyzeAnother: () => void
}) {
  const { toast } = useToast()
  const analysis = doc.analysis
  const [reportState, setReportState] = useState<"idle" | "loading" | "error">("idle")

  const findings = useMemo(
    () => findingsBySeverity(analysis?.findings ?? []),
    [analysis],
  )

  const clausesById = useMemo(() => {
    const map = new Map<number, (typeof doc.clauses)[number]>()
    for (const clause of doc.clauses) map.set(clause.id, clause)
    return map
  }, [doc.clauses])

  const level = toRiskLevel(doc.risk_level) ?? riskLevelFromScoreOrNull(doc.risk_score)
  const safety = Math.round(
    doc.safety_score ?? (doc.risk_score !== null ? 100 - doc.risk_score : 0),
  )
  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
    for (const finding of findings) {
      const key = (toRiskLevel(finding.severity) ?? "low").toUpperCase()
      counts[key] = (counts[key] ?? 0) + 1
    }
    return counts
  }, [findings])

  const defaultOpen = useMemo(
    () =>
      findings
        .filter((finding) => finding.severity === "CRITICAL" || finding.severity === "HIGH")
        .map((finding) => String(finding.id))[0],
    [findings],
  )

  const handleDownload = useCallback(async () => {
    setReportState("loading")
    try {
      const blob = await downloadAnalysisReport(doc.id)
      downloadBlob(blob, `juriscan-analysis-${doc.id}.pdf`)
      setReportState("idle")
      toast({
        title: "Report downloaded",
        description: "The PDF analysis report was downloaded.",
        variant: "success",
      })
    } catch (error) {
      setReportState("error")
      toast({
        title: "Download failed",
        description: error instanceof ApiError ? error.message : "The report could not be generated.",
        variant: "destructive",
      })
    }
  }, [doc.id, toast])

  if (doc.status !== "PROCESSED" || !analysis) {
    return (
      <EmptyState
        icon={FileText}
        title={
          doc.status === "FAILED" ? "Analysis failed" : `Analysis ${doc.status.toLowerCase()}`
        }
        description={
          doc.status === "FAILED"
            ? (doc.error_message ?? "This document could not be processed. Try uploading it again.")
            : "Results will appear here once processing completes."
        }
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{formatFileType(doc.file_type)}</Badge>
              <StatusBadge status={doc.status} />
              <Badge variant="secondary">{analysis.model_name}</Badge>
              <span className="font-mono text-xs text-muted-foreground">#{doc.id}</span>
            </div>
            <p className="truncate text-xl font-semibold tracking-tight" title={doc.filename}>
              {doc.filename}
            </p>
            <p className="text-xs text-muted-foreground">
              Analyzed {formatDateTime(analysis.completed_at ?? doc.created_at)}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button variant="outline" onClick={onAnalyzeAnother}>
              <FileText aria-hidden="true" />
              Analyze another document
            </Button>
            <Button onClick={() => void handleDownload()} disabled={reportState === "loading"}>
              {reportState === "loading" ? (
                <Loader2 className="animate-spin" aria-hidden="true" />
              ) : (
                <Download aria-hidden="true" />
              )}
              Download Full Analysis Report (PDF)
            </Button>
          </div>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Overall assessment</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
          <RiskScore score={safety} level={level} label="Legal safety score" />
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Overall risk level</span>
              {level ? <SeverityBadge level={level} /> : <Badge variant="outline">Not analyzed</Badge>}
            </div>

            <div className="flex items-center gap-3">
              <Progress value={safety} className="h-2.5" />
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {safety}/100
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {RISK_LEVELS.map((risk) => (
                <div
                  key={risk}
                  className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs"
                >
                  <span
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: RISK_META[risk].hex }}
                    aria-hidden="true"
                  />
                  {RISK_META[risk].label}
                  <span className="font-medium">{severityCounts[risk.toUpperCase()] ?? 0}</span>
                </div>
              ))}
            </div>

            <div className="grid max-w-xs grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Findings</p>
                <p className="text-xl font-semibold">{findings.length}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Critical / High</p>
                <p className="text-xl font-semibold">
                  {(severityCounts.CRITICAL ?? 0) + (severityCounts.HIGH ?? 0)}
                </p>
              </div>
            </div>

            <p className="border-t border-border pt-3 text-xs text-muted-foreground">
              Legal safety starts at 100 and each finding subtracts its severity weight
              (LOW −4, MEDIUM −10, HIGH −20, CRITICAL −35), floored at 0. Automated
              preliminary review. This score is not a legal opinion or a guarantee of
              enforceability.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What this means for you</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {executiveSummary(doc).map((paragraph) => (
            <p key={paragraph} className="text-sm leading-relaxed text-muted-foreground">
              {paragraph}
            </p>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            Issues to review
            {findings.length > 0 ? (
              <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-xs font-normal text-muted-foreground">
                {findings.length}
              </span>
            ) : null}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {findings.length === 0 ? (
            <EmptyState
              icon={SearchCheck}
              title="No issues were flagged by this automated review"
              description="The rule-based baseline did not detect the patterns it checks for. This is not a guarantee that the contract is legally safe."
            />
          ) : (
            <Accordion type="single" collapsible defaultValue={defaultOpen}>
              {findings.map((finding) => {
                const findingLevel = toRiskLevel(finding.severity) ?? "low"
                const clause = finding.clause_id ? clausesById.get(finding.clause_id) : undefined
                const clauseText = clause?.text ?? null
                return (
                  <AccordionItem key={finding.id} value={String(finding.id)}>
                    <AccordionTrigger className="gap-4">
                      <div className="flex min-w-0 flex-col gap-1.5">
                        <span className="flex flex-wrap items-center gap-2">
                          <SeverityBadge level={findingLevel} />
                          <span className="font-medium text-foreground">{finding.title}</span>
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {findingClauseRef(finding)}
                          {finding.description
                            ? ` - ${finding.description}`
                            : null}
                        </span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="flex flex-col gap-4 px-1">
                        <div>
                          <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                            Original contract wording
                          </p>
                          {clauseText ? (
                            <blockquote
                              className="rounded-r-lg border-l-4 bg-muted/50 px-4 py-3 text-sm italic leading-relaxed"
                              style={{ borderLeftColor: RISK_META[findingLevel].hex }}
                            >
                              {clauseText}
                            </blockquote>
                          ) : (
                            <p className="text-sm text-muted-foreground">
                              Exact clause text was not available in the extracted document.
                            </p>
                          )}
                          {clause?.heading ? (
                            <p className="mt-1.5 text-xs text-muted-foreground">
                              Section: {clause.heading}
                            </p>
                          ) : null}
                        </div>
                        <div>
                          <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                            Why it was flagged
                          </p>
                          <p className="text-sm">{finding.description}</p>
                        </div>
                        <div>
                          <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                            What it could mean for you
                          </p>
                          <p className="text-sm">{severityImpactText(finding.severity)}</p>
                        </div>
                        <div>
                          <p className="mb-1.5 text-xs font-medium text-muted-foreground">
                            Suggested next step
                          </p>
                          <p className="text-sm">
                            {finding.recommendation ??
                              "Review this clause with a legal professional before signing."}
                          </p>
                        </div>
                        {finding.citation ? (
                          <p className="text-xs text-muted-foreground">
                            Reference: {finding.citation}
                          </p>
                        ) : null}
                        {finding.rule_code ? (
                          <span className="w-fit rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                            {finding.rule_code}
                          </span>
                        ) : null}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                )
              })}
            </Accordion>
          )}
        </CardContent>
      </Card>

      <p className="text-center text-xs text-muted-foreground">
        Automated preliminary review. This score is not a legal opinion or a guarantee of
        enforceability.
      </p>
    </div>
  )
}