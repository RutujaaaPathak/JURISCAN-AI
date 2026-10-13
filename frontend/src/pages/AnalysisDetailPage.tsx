import {
  ArrowLeft,
  Calendar,
  Download,
  FileText,
  Globe2,
  Info,
  ListChecks,
  Loader2,
  ScrollText,
  ShieldAlert,
  TextSearch,
} from "lucide-react"
import { useCallback, useMemo, useState } from "react"
import { Link, useParams } from "react-router-dom"

import { ClauseCard } from "@/components/analysis/ClauseCard"
import { ExtractedTextViewer } from "@/components/analysis/ExtractedTextViewer"
import { RiskScore } from "@/components/analysis/RiskScore"
import { SeverityBadge, StatusBadge } from "@/components/analysis/RiskBadges"
import { CategoryBars } from "@/components/charts/Charts"
import { EmptyState, ErrorState, LoadingState } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/components/ui/toast"
import { useAsync } from "@/hooks/useAsync"
import { downloadAnalysisReport, downloadBlob, getDocument } from "@/lib/documents"
import { ApiError } from "@/lib/api"
import { formatDateTime, formatFileType } from "@/lib/format"
import { RISK_LEVELS, RISK_META, riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"
import type { DocumentDetail } from "@/lib/types"

function DetailBody({ doc }: { doc: DocumentDetail }) {
  const analysis = doc.analysis
  const [tab, setTab] = useState("findings")
  const [focusClause, setFocusClause] = useState<{ id: number; nonce: number } | null>(
    null,
  )
  const [exporting, setExporting] = useState(false)
  const { toast } = useToast()

  const handleExport = useCallback(async () => {
    setExporting(true)
    try {
      const blob = await downloadAnalysisReport(doc.id)
      downloadBlob(blob, `juriscan-analysis-${doc.id}.pdf`)
      toast({
        title: "Report downloaded",
        description: "The PDF analysis report was saved to your downloads.",
        variant: "success",
      })
    } catch (error) {
      toast({
        title: "Could not export report",
        description: error instanceof ApiError ? error.message : "Please try again.",
        variant: "destructive",
      })
    } finally {
      setExporting(false)
    }
  }, [doc.id, toast])

  const viewClauseInText = useCallback((clauseId?: number | null) => {
    if (clauseId === null || clauseId === undefined) return
    setTab("text")
    setFocusClause((previous) => ({
      id: clauseId,
      nonce: (previous?.nonce ?? 0) + 1,
    }))
  }, [])

  const findings = useMemo(
    () =>
      [...(analysis?.findings ?? [])].sort(
        (a, b) => (RISK_META[toRiskLevel(b.severity) ?? "low"].order) - (RISK_META[toRiskLevel(a.severity) ?? "low"].order),
      ),
    [analysis],
  )

  const clausesById = useMemo(() => {
    const map = new Map<number, (typeof doc.clauses)[number]>()
    for (const clause of doc.clauses) map.set(clause.id, clause)
    return map
  }, [doc.clauses])

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
    for (const finding of findings) {
      const key = (toRiskLevel(finding.severity) ?? "low").toUpperCase()
      counts[key] = (counts[key] ?? 0) + 1
    }
    return counts
  }, [findings])

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const finding of findings) {
      const clause = finding.clause_id ? clausesById.get(finding.clause_id) : undefined
      const category = clause?.clause_type ?? finding.rule_code ?? "General"
      counts.set(category, (counts.get(category) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([category, count]) => ({ category, count }))
      .sort((a, b) => b.count - a.count)
  }, [findings, clausesById])

  const level = toRiskLevel(doc.risk_level) ?? riskLevelFromScoreOrNull(doc.risk_score)

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to="/dashboard/documents">
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to documents
        </Link>
      </Button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{doc.title}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{formatFileType(doc.file_type)}</Badge>
            <StatusBadge status={doc.status} />
            {analysis ? <Badge variant="secondary">{analysis.model_name}</Badge> : null}
            <span className="font-mono text-xs text-muted-foreground">#{doc.id}</span>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => void handleExport()} disabled={exporting}>
          {exporting ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Download className="size-4" aria-hidden="true" />
          )}
          Export report
        </Button>
      </div>

      {analysis?.summary ? (
        <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
          {analysis.summary}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <CardContent className="grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
              <RiskScore
                score={Math.round(doc.safety_score ?? (doc.risk_score !== null ? 100 - doc.risk_score : 0))}
                level={level}
                label="Legal safety score"
              />
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">Overall risk level</span>
                  {level ? <SeverityBadge level={level} /> : <Badge variant="outline">Not analyzed</Badge>}
                </div>
                <div className="grid grid-cols-2 gap-4">
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
                  <div className="col-span-2 flex flex-wrap gap-2">
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
                </div>
                <p className="border-t border-border pt-3 text-xs text-muted-foreground">
                  Legal safety scores how clean the contract looks: 100 = no risk indicators detected.
                  Every finding subtracts its severity weight (LOW −4, MEDIUM −10, HIGH −20, CRITICAL −35),
                  floored at 0. It is the inverse of the rule-based risk score and a screening aid — not a
                  legal opinion.
                </p>
              </div>
            </CardContent>
          </Card>

          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="findings">
                <ShieldAlert className="size-4" aria-hidden="true" />
                Findings
              </TabsTrigger>
              <TabsTrigger value="recommendations">
                <ListChecks className="size-4" aria-hidden="true" />
                Recommendations
              </TabsTrigger>
              <TabsTrigger value="text">
                <ScrollText className="size-4" aria-hidden="true" />
                Extracted text
              </TabsTrigger>
            </TabsList>

            <TabsContent value="findings" className="mt-4 flex flex-col gap-4">
              {findings.length === 0 ? (
                <EmptyState
                  icon={ShieldAlert}
                  title="No risk indicators detected"
                  description="The rule-based baseline found no matching patterns in this document."
                />
              ) : (
                findings.map((finding) => {
                  const clause = finding.clause_id ? clausesById.get(finding.clause_id) : undefined
                  return (
                    <ClauseCard
                      key={finding.id}
                      finding={finding}
                      clauseText={clause?.text}
                      onViewInText={viewClauseInText}
                    />
                  )
                })
              )}
            </TabsContent>

            <TabsContent value="recommendations" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Recommended actions</CardTitle>
                </CardHeader>
                <CardContent>
                  {findings.some((finding) => finding.recommendation) ? (
                    <ul className="flex flex-col divide-y divide-border">
                      {findings
                        .filter((finding) => finding.recommendation)
                        .map((finding) => (
                          <li key={finding.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                            <SeverityBadge
                              level={toRiskLevel(finding.severity) ?? "low"}
                              className="mt-0.5 shrink-0"
                            />
                            <div>
                              <p className="text-sm">{finding.recommendation}</p>
                              <p className="text-xs text-muted-foreground">
                                {finding.title}
                                {finding.clause_number !== null ? ` · Clause ${finding.clause_number}` : ""}
                              </p>
                            </div>
                          </li>
                        ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No recommendations were generated for this document.
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="text" className="mt-4">
              <Card>
                <CardHeader className="flex-row items-center gap-2">
                  <ScrollText className="size-4 text-muted-foreground" aria-hidden="true" />
                  <CardTitle>Extracted text</CardTitle>
                </CardHeader>
                <CardContent>
                  <ExtractedTextViewer
                    text={doc.text_content}
                    pages={doc.pages}
                    clauses={doc.clauses}
                    focusClauseId={focusClause?.id ?? null}
                    focusNonce={focusClause?.nonce ?? 0}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          <Card>
            <CardHeader className="flex-row items-center gap-2">
              <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
              <CardTitle>Clauses ({doc.clauses.length})</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {doc.clauses.map((clause) => {
                const clauseLevel = toRiskLevel(clause.risk_level)
                const nestIndent = clause.level && clause.level > 1 ? Math.min((clause.level - 1) * 16, 48) : 0
                return (
                  <div
                    key={clause.id}
                    className="rounded-lg border border-border p-3"
                    style={nestIndent > 0 ? { marginLeft: `${nestIndent}px` } : undefined}
                  >
                    <div className="mb-1.5 flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-muted-foreground">
                        Clause {clause.clause_number}
                      </span>
                      {clause.label ? (
                        <Badge variant="secondary" className="font-mono text-[10px]">
                          {clause.label}
                        </Badge>
                      ) : null}
                      {clause.level && clause.level > 1 ? (
                        <span className="text-[10px] text-muted-foreground font-mono">
                          L{clause.level}
                        </span>
                      ) : null}
                      {clause.heading ? (
                        <span className="truncate text-sm font-medium">{clause.heading}</span>
                      ) : null}
                      {clauseLevel ? <SeverityBadge level={clauseLevel} /> : null}
                      {clause.page_number ? (
                        <span className="text-xs text-muted-foreground">Page {clause.page_number}</span>
                      ) : null}
                      {clause.clause_type ? <Badge variant="outline">{clause.clause_type}</Badge> : null}
                      <Button
                        variant="ghost"
                        size="xs"
                        className="ml-auto"
                        onClick={() => viewClauseInText(clause.id)}
                      >
                        <TextSearch aria-hidden="true" />
                        View in text
                      </Button>
                    </div>
                    <p className="line-clamp-3 text-sm text-muted-foreground">{clause.text}</p>
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Document details</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              <div className="flex items-center gap-2">
                <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
                <span className="truncate">{doc.filename}</span>
              </div>
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-muted-foreground" aria-hidden="true" />
                <span className="text-muted-foreground">Status</span>
                <StatusBadge status={doc.status} />
              </div>
              <div className="flex items-center gap-2">
                <Info className="size-4 text-muted-foreground" aria-hidden="true" />
                <span>
                  {formatFileType(doc.file_type)}
                  {doc.page_count !== null ? ` · ${doc.page_count} page(s)` : " · page count unavailable"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Globe2 className="size-4 text-muted-foreground" aria-hidden="true" />
                <span>{doc.language ?? "Unknown language"}</span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="size-4 text-muted-foreground" aria-hidden="true" />
                <span>{formatDateTime(doc.created_at)}</span>
              </div>
              {doc.extracted_at ? (
                <div className="flex items-center gap-2">
                  <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
                  <span className="text-muted-foreground">
                    Extracted {formatDateTime(doc.extracted_at)}
                  </span>
                </div>
              ) : null}
              <dl className="grid grid-cols-2 gap-3 border-t border-border pt-3">
                <div>
                  <dt className="text-xs text-muted-foreground">Words</dt>
                  <dd className="font-medium">{(doc.word_count ?? 0).toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Clauses</dt>
                  <dd className="font-medium">{doc.clauses.length}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Risk score</dt>
                  <dd className="font-medium">
                    {doc.risk_score !== null ? `${Math.round(doc.risk_score)}/100` : "—"}
                    {level ? ` · ${RISK_META[level].label}` : ""}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">High risk</dt>
                  <dd className="font-medium">{doc.high_risk_count}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          {categoryCounts.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Findings by category</CardTitle>
              </CardHeader>
              <CardContent>
                <CategoryBars data={categoryCounts.map((entry) => ({ label: entry.category, value: entry.count }))} />
              </CardContent>
            </Card>
          ) : null}

          {analysis?.completed_at ? (
            <Card>
              <CardHeader>
                <CardTitle>Analysis</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Engine</span>
                  <span className="font-medium">{analysis.model_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <StatusBadge status={analysis.status} />
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Completed</span>
                  <span>{formatDateTime(analysis.completed_at)}</span>
                </div>
                <p className="border-t border-border pt-2 text-xs text-muted-foreground">
                  Rule-based, explainable analysis. No trained model (such as Legal-BERT) was used.
                </p>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>()
  const loader = useCallback(() => getDocument(id ?? ""), [id])
  const { state, refresh } = useAsync(loader)

  const notFound =
    state.phase === "error" &&
    (state.errorCode === "document_not_found" || state.errorStatus === 404)

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to="/dashboard/documents">
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to documents
        </Link>
      </Button>

      {state.phase === "loading" || state.phase === "idle" ? (
        <LoadingState label="Loading analysis…" />
      ) : notFound ? (
        <EmptyState
          icon={FileText}
          title="Analysis not found"
          description={`No document matches the id "${id}".`}
          action={
            <Button asChild variant="outline" size="sm">
              <Link to="/dashboard/documents">Back to documents</Link>
            </Button>
          }
        />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load analysis"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : state.data ? (
        state.data.status === "PROCESSED" ? (
          <DetailBody doc={state.data} />
        ) : (
          <EmptyState
            icon={ShieldAlert}
            title={
              state.data.status === "FAILED"
                ? "Analysis failed"
                : `Analysis ${state.data.status.toLowerCase()}`
            }
            description={
              state.data.status === "FAILED"
                ? (state.data.error_message ??
                  "This document could not be processed. Try uploading it again.")
                : "Findings will appear here once processing completes."
            }
          />
        )
      ) : null}
    </div>
  )
}
