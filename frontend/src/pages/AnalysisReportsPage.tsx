import { ClipboardList, FileText, RefreshCw, ShieldAlert } from "lucide-react"
import { useCallback } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge } from "@/components/analysis/RiskBadges"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { StatCard } from "@/components/dashboard/StatCard"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useAsync } from "@/hooks/useAsync"
import { listDocuments } from "@/lib/documents"
import { formatDate, formatFileType } from "@/lib/format"
import { riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"

export function AnalysisReportsPage() {
  const loader = useCallback(() => listDocuments({ status: "PROCESSED", limit: 200 }), [])
  const { state, refresh } = useAsync(loader)

  const reports = state.data?.items ?? []
  const highRisk = reports.filter(
    (doc) => doc.risk_level === "HIGH" || doc.risk_level === "CRITICAL",
  ).length
  const scored = reports.filter((doc) => doc.risk_score !== null)
  const avgRisk =
    scored.length > 0
      ? Math.round(scored.reduce((sum, doc) => sum + (doc.risk_score ?? 0), 0) / scored.length)
      : 0

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Analysis reports</h1>
          <p className="text-sm text-muted-foreground">
            Completed analyses with their risk score, findings and detected issues.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void refresh()}
          disabled={state.phase === "loading"}
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {state.phase === "ok" && reports.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Reports" value={reports.length} icon={ClipboardList} />
          <StatCard
            label="High-risk reports"
            value={highRisk}
            hint="High and critical"
            icon={ShieldAlert}
            tone="destructive"
          />
          <StatCard
            label="Average risk score"
            value={avgRisk}
            hint="Across completed analyses"
            tone={avgRisk >= 50 ? "warning" : "success"}
          />
        </div>
      ) : null}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>
            {state.phase === "ok" ? `${reports.length} report(s)` : "Reports"}
          </CardTitle>
          {state.lastUpdated && state.phase === "ok" ? (
            <span className="text-xs text-muted-foreground">
              Updated {state.lastUpdated.toLocaleTimeString()}
            </span>
          ) : null}
        </CardHeader>
        <CardContent>
          {state.phase === "loading" || state.phase === "idle" ? (
            <LoadingSkeleton rows={5} />
          ) : state.phase === "error" ? (
            <ErrorState
              title="Could not load reports"
              description={state.error ?? undefined}
              onRetry={() => void refresh()}
            />
          ) : reports.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="No reports yet"
              description="Once a document finishes analysis, its report will appear here."
              action={
                <Button asChild size="sm">
                  <Link to="/dashboard/upload">Upload document</Link>
                </Button>
              }
            />
          ) : (
            <div className="overflow-hidden rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Document</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead>Risk</TableHead>
                    <TableHead className="hidden lg:table-cell">Findings</TableHead>
                    <TableHead className="hidden lg:table-cell">Uploaded</TableHead>
                    <TableHead className="text-right">Report</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reports.map((doc) => {
                    const level =
                      toRiskLevel(doc.risk_level) ?? riskLevelFromScoreOrNull(doc.risk_score)
                    return (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="flex items-center gap-2.5">
                            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                              <FileText
                                className="size-4 text-muted-foreground"
                                aria-hidden="true"
                              />
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">{doc.title}</p>
                              <p className="truncate text-xs text-muted-foreground">
                                {doc.filename}
                              </p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge variant="outline">{formatFileType(doc.file_type)}</Badge>
                        </TableCell>
                        <TableCell>
                          {level ? (
                            <div className="flex items-center gap-2">
                              <SeverityBadge level={level} />
                              <span className="text-xs text-muted-foreground">
                                {Math.round(doc.risk_score ?? 0)}
                              </span>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                          {doc.finding_count} ({doc.high_risk_count} high)
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                          {formatDate(doc.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="outline" size="sm" asChild>
                            <Link to={`/dashboard/analyses/${doc.id}`}>View report</Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
