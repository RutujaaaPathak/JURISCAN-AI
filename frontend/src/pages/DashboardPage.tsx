import {
  Activity,
  ArrowRight,
  Database,
  FileCheck2,
  FileText,
  Gauge,
  Server,
  ShieldAlert,
  Upload,
} from "lucide-react"
import { useCallback, useEffect } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge, StatusBadge } from "@/components/analysis/RiskBadges"
import { BarChart, CategoryBars, DonutChart } from "@/components/charts/Charts"
import { DemoNotice } from "@/components/common/DemoNotice"
import { EmptyState, ErrorState, LoadingSkeleton, LoadingState } from "@/components/common/States"
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
import { useHealth } from "@/hooks/useHealth"
import { useStatus } from "@/hooks/useStatus"
import { API_BASE_URL } from "@/lib/api"
import { DOCUMENTS_CHANGED_EVENT, getOverviewStats, listDocuments } from "@/lib/documents"
import { formatDayLabel, formatFileType } from "@/lib/format"
import type { RiskLevel } from "@/lib/risk"
import { RISK_LEVELS, RISK_META, riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"
import type { DocumentSummary, OverviewStats } from "@/lib/types"
import {
  categoryCounts,
  documentRiskLevel,
  documents,
  overallStats,
  riskDistribution,
  uploadTrend,
} from "@/data/demo"

interface RecentRow {
  id: number | string
  title: string
  filename: string
  fileType: string
  status: string
  level: RiskLevel | null
  score: number | null
}

interface DashboardData {
  analyzed: number
  total: number
  avgRisk: number
  highRiskFindings: number
  inPipeline: number
  failed: number
  distribution: Record<RiskLevel, number>
  categories: { label: string; value: number }[]
  trend: { label: string; value: number }[]
  recent: RecentRow[]
}

function emptyDistribution(): Record<RiskLevel, number> {
  return { low: 0, medium: 0, high: 0, critical: 0 }
}

function fromStats(stats: OverviewStats, recent: DocumentSummary[]): DashboardData {
  return {
    analyzed: stats.processed,
    total: stats.total_documents,
    avgRisk: Math.round(stats.avg_risk_score),
    highRiskFindings: stats.high_risk_findings,
    inPipeline: stats.processing,
    failed: stats.failed,
    distribution: RISK_LEVELS.reduce((acc, level) => {
      acc[level] = stats.risk_distribution[level.toUpperCase()] ?? 0
      return acc
    }, emptyDistribution()),
    categories: stats.category_counts.map((entry) => ({ label: entry.category, value: entry.count })),
    trend: stats.upload_trend.map((entry) => ({ label: formatDayLabel(entry.date), value: entry.count })),
    recent: recent.map((doc) => ({
      id: doc.id,
      title: doc.title,
      filename: doc.filename,
      fileType: formatFileType(doc.file_type),
      status: doc.status,
      level: toRiskLevel(doc.risk_level) ?? riskLevelFromScoreOrNull(doc.risk_score),
      score: doc.risk_score,
    })),
  }
}

const DEMO_STATUS: Record<string, string> = {
  analyzed: "PROCESSED",
  review: "PROCESSED",
  processing: "PROCESSING",
  queued: "PENDING",
}

function fromDemo(): DashboardData {
  const stats = overallStats()
  const distribution = riskDistribution()
  return {
    analyzed: stats.analyzed,
    total: stats.totalDocuments,
    avgRisk: stats.avgRisk,
    highRiskFindings: stats.highRiskFindings,
    inPipeline: stats.inPipeline,
    failed: 0,
    distribution: RISK_LEVELS.reduce((acc, level) => {
      acc[level] = distribution[level]
      return acc
    }, emptyDistribution()),
    categories: categoryCounts()
      .slice(0, 6)
      .map((entry) => ({ label: entry.category, value: entry.count })),
    trend: uploadTrend.map((entry) => ({ label: entry.label, value: entry.value })),
    recent: [...documents]
      .sort((a, b) => b.uploadedAt.localeCompare(a.uploadedAt))
      .slice(0, 5)
      .map((doc) => ({
        id: doc.id,
        title: doc.title,
        filename: doc.fileName,
        fileType: doc.docType,
        status: DEMO_STATUS[doc.status] ?? doc.status,
        level: documentRiskLevel(doc),
        score: doc.riskScore,
      })),
  }
}

function Overview({ data, isDemo }: { data: DashboardData; isDemo: boolean }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Documents analyzed"
          value={data.analyzed}
          hint={`${data.total} total uploaded`}
          icon={FileCheck2}
        />
        <StatCard
          label="Average risk score"
          value={data.avgRisk}
          hint="Across analyzed documents"
          icon={Gauge}
          tone={data.avgRisk >= 50 ? "warning" : "success"}
        />
        <StatCard
          label="High-risk findings"
          value={data.highRiskFindings}
          hint="High and critical severity"
          icon={ShieldAlert}
          tone="destructive"
        />
        <StatCard
          label="In pipeline"
          value={data.inPipeline}
          hint={`${data.failed} failed`}
          icon={Activity}
          tone="warning"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Risk distribution</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-5">
            <DonutChart
              data={RISK_LEVELS.map((level) => ({
                label: RISK_META[level].label,
                value: data.distribution[level],
                color: RISK_META[level].hex,
              }))}
              centerLabel="documents"
            />
            <ul className="grid w-full grid-cols-2 gap-2">
              {RISK_LEVELS.map((level) => (
                <li key={level} className="flex items-center gap-2 text-sm">
                  <span
                    className="size-2.5 rounded-full"
                    style={{ backgroundColor: RISK_META[level].hex }}
                    aria-hidden="true"
                  />
                  <span className="text-muted-foreground">{RISK_META[level].label}</span>
                  <span className="ml-auto font-medium">{data.distribution[level]}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Findings by category</CardTitle>
            {isDemo ? <Badge variant="secondary">Sample</Badge> : null}
          </CardHeader>
          <CardContent>
            {data.categories.length > 0 ? (
              <CategoryBars data={data.categories} />
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No categorized findings yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Upload activity</CardTitle>
          {isDemo ? <Badge variant="secondary">Sample</Badge> : null}
        </CardHeader>
        <CardContent>
          {data.trend.length > 0 ? (
            <BarChart data={data.trend} valueSuffix="" height={140} />
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">No uploads recorded yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Recent documents</CardTitle>
          <Button asChild variant="ghost" size="sm">
            <Link to="/dashboard/documents">
              View all
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {data.recent.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No documents yet"
              description="Upload a contract to see it appear here."
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
                    <TableHead>Status</TableHead>
                    <TableHead>Risk</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.recent.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                            <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">{doc.title}</p>
                            <p className="truncate text-xs text-muted-foreground">{doc.filename}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Badge variant="outline">{doc.fileType}</Badge>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={doc.status} />
                      </TableCell>
                      <TableCell>
                        {doc.level ? (
                          <div className="flex items-center gap-2">
                            <SeverityBadge level={doc.level} />
                            <span className="text-xs text-muted-foreground">
                              {Math.round(doc.score ?? 0)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {doc.status === "PROCESSED" && !isDemo ? (
                          <Button variant="ghost" size="sm" asChild>
                            <Link to={`/dashboard/analyses/${doc.id}`}>View</Link>
                          </Button>
                        ) : (
                          <Button variant="ghost" size="sm" disabled>
                            View
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  )
}

export function DashboardPage() {
  const { state: health, refresh: refreshHealth } = useHealth()
  const { state: status, refresh: refreshStatus } = useStatus()

  const statsLoader = useCallback(() => getOverviewStats(), [])
  const recentLoader = useCallback(() => listDocuments({ limit: 5 }), [])
  const { state: stats, refresh: refreshStats } = useAsync(statsLoader)
  const { state: recent, refresh: refreshRecent } = useAsync(recentLoader)

  useEffect(() => {
    const handleDocumentsChanged = () => {
      void refreshStats()
      void refreshRecent()
    }
    window.addEventListener(DOCUMENTS_CHANGED_EVENT, handleDocumentsChanged)
    return () => window.removeEventListener(DOCUMENTS_CHANGED_EVENT, handleDocumentsChanged)
  }, [refreshStats, refreshRecent])

  const isEmpty = stats.phase === "ok" && stats.data !== null && stats.data.total_documents === 0
  const useDemo = isEmpty

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Portfolio health across contracts, clauses and detected risk.
          </p>
        </div>
        <Button asChild>
          <Link to="/dashboard/upload">
            <Upload className="size-4" aria-hidden="true" />
            Upload document
          </Link>
        </Button>
      </div>

      {useDemo ? <DemoNotice /> : null}

      {stats.phase === "loading" || stats.phase === "idle" ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <LoadingSkeleton key={index} rows={1} />
          ))}
        </div>
      ) : stats.phase === "error" ? (
        <ErrorState
          title="Could not load overview"
          description={stats.error ?? undefined}
          onRetry={() => void refreshStats()}
        />
      ) : useDemo ? (
        <Overview data={fromDemo()} isDemo />
      ) : stats.data ? (
        <Overview data={fromStats(stats.data, recent.data?.items ?? [])} isDemo={false} />
      ) : null}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Live system status</CardTitle>
          <Badge variant="outline">
            <Server className="size-3" aria-hidden="true" />
            {API_BASE_URL}
          </Badge>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-border p-4">
            <p className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Activity className="size-4 text-muted-foreground" aria-hidden="true" />
              Backend
            </p>
            {health.phase === "loading" || health.phase === "idle" ? (
              <LoadingState label="Contacting backend…" />
            ) : health.phase === "error" ? (
              <ErrorState
                title="Backend unreachable"
                description={health.error ?? undefined}
                onRetry={() => void refreshHealth()}
              />
            ) : (
              <dl className="flex flex-col gap-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="font-medium capitalize">{health.data?.status}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Environment</dt>
                  <dd className="font-medium">{health.data?.environment}</dd>
                </div>
              </dl>
            )}
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Database className="size-4 text-muted-foreground" aria-hidden="true" />
              Database
            </p>
            {status.phase === "loading" || status.phase === "idle" ? (
              <LoadingState label="Checking services…" />
            ) : status.phase === "error" ? (
              <ErrorState
                title="Status unavailable"
                description={status.error ?? undefined}
                onRetry={() => void refreshStatus()}
              />
            ) : (
              <dl className="flex flex-col gap-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Overall</dt>
                  <dd className="font-medium capitalize">{status.data?.status}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-muted-foreground">Connection</dt>
                  <dd>
                    <Badge variant={status.data?.database === "ok" ? "success" : "destructive"}>
                      {status.data?.database ?? "unknown"}
                    </Badge>
                  </dd>
                </div>
              </dl>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
