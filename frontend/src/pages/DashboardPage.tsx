import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCheck2,
  FileText,
  Gauge,
  Gavel,
  MessageSquare,
  Server,
  Settings,
  ShieldAlert,
  Upload,
} from "lucide-react"
import { useCallback } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge, StatusBadge } from "@/components/analysis/RiskBadges"
import { CategoryBars, DonutChart } from "@/components/charts/Charts"
import { EmptyState, ErrorState, LoadingSkeleton, LoadingState } from "@/components/common/States"
import { ActivityFeed } from "@/components/dashboard/ActivityFeed"
import type { ActivityItem } from "@/components/dashboard/ActivityFeed"
import { QuickActions } from "@/components/dashboard/QuickActions"
import type { QuickAction } from "@/components/dashboard/QuickActions"
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
import { useRole } from "@/context/RoleContext"
import { useAsync } from "@/hooks/useAsync"
import type { AsyncPhase } from "@/hooks/useAsync"
import { useHealth } from "@/hooks/useHealth"
import { useStatus } from "@/hooks/useStatus"
import { API_BASE_URL } from "@/lib/api"
import { getOverviewStats, listDocuments } from "@/lib/documents"
import { formatFileType } from "@/lib/format"
import { RISK_LEVELS, RISK_META, riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"
import { ROLE_META } from "@/lib/roles"
import type { DocumentSummary, OverviewStats } from "@/lib/types"

const QUICK_ACTIONS: QuickAction[] = [
  { label: "Upload Documents", description: "Add a contract to review", icon: Upload, to: "/dashboard/upload" },
  { label: "My Documents", description: "Browse uploaded contracts", icon: FileText, to: "/dashboard/documents" },
  { label: "Analysis Reports", description: "Review completed analyses", icon: ClipboardList, to: "/dashboard/reports" },
  { label: "Find Legal Help", description: "Directory and cases", icon: Gavel, to: "/dashboard/legal-help" },
  { label: "Messages", description: "Conversations", icon: MessageSquare, to: "/dashboard/messages" },
  { label: "Settings", description: "Profile and preferences", icon: Settings, to: "/dashboard/settings" },
]

function buildActivity(items: DocumentSummary[]): ActivityItem[] {
  const events: ActivityItem[] = []
  for (const doc of items) {
    events.push({
      id: `upload-${doc.id}`,
      title: "Document uploaded",
      description: doc.title,
      timestamp: doc.created_at,
      icon: Upload,
      tone: "default",
    })
    if (doc.extracted_at) {
      events.push({
        id: `extract-${doc.id}`,
        title: "Text extracted",
        description: doc.title,
        timestamp: doc.extracted_at,
        icon: FileText,
        tone: "default",
      })
    }
    if (doc.status === "FAILED") {
      events.push({
        id: `failed-${doc.id}`,
        title: "Processing failed",
        description: doc.error_message ?? doc.title,
        timestamp: doc.updated_at,
        icon: AlertTriangle,
        tone: "destructive",
      })
    } else if (doc.status === "PROCESSED") {
      events.push({
        id: `analyzed-${doc.id}`,
        title: "Analysis completed",
        description:
          doc.risk_score !== null
            ? `${doc.title} · risk ${Math.round(doc.risk_score)}/100`
            : doc.title,
        timestamp: doc.updated_at,
        icon: CheckCircle2,
        tone: "success",
      })
    }
  }
  return events
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 6)
}

interface DocsView {
  phase: AsyncPhase
  items: DocumentSummary[]
  error: string | null
  onRetry: () => void
}

function RecentDocuments({ docs }: { docs: DocsView }) {
  return (
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
        {docs.phase === "loading" || docs.phase === "idle" ? (
          <LoadingSkeleton rows={4} />
        ) : docs.phase === "error" ? (
          <ErrorState
            title="Could not load recent documents"
            description={docs.error ?? undefined}
            onRetry={docs.onRetry}
          />
        ) : docs.items.length === 0 ? (
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
                {docs.items.map((doc) => {
                  const level =
                    toRiskLevel(doc.risk_level) ?? riskLevelFromScoreOrNull(doc.risk_score)
                  const processed = doc.status === "PROCESSED"
                  return (
                    <TableRow key={doc.id}>
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                            <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
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
                        <StatusBadge status={doc.status} />
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
                      <TableCell className="text-right">
                        {processed ? (
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
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function RecentActivity({ docs }: { docs: DocsView }) {
  if (docs.phase === "loading" || docs.phase === "idle") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
        </CardHeader>
        <CardContent>
          <LoadingSkeleton rows={4} />
        </CardContent>
      </Card>
    )
  }

  if (docs.phase === "error") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorState
            title="Could not load activity"
            description={docs.error ?? undefined}
            onRetry={docs.onRetry}
          />
        </CardContent>
      </Card>
    )
  }

  return (
    <ActivityFeed
      items={buildActivity(docs.items)}
      empty={
        <EmptyState
          icon={Activity}
          title="No activity yet"
          description="Upload and analyze a document to build an activity trail."
        />
      }
    />
  )
}

function Overview({ stats, docs }: { stats: OverviewStats; docs: DocsView }) {
  const distribution = RISK_LEVELS.map((level) => ({
    label: RISK_META[level].label,
    value: stats.risk_distribution[level.toUpperCase()] ?? 0,
    color: RISK_META[level].hex,
  }))
  const categories = stats.category_counts.map((entry) => ({
    label: entry.category,
    value: entry.count,
  }))
  const avgRisk = Math.round(stats.avg_risk_score)

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Documents analyzed"
          value={stats.processed}
          hint={`${stats.total_documents} total uploaded`}
          icon={FileCheck2}
        />
        <StatCard
          label="Average risk score"
          value={avgRisk}
          hint="Across analyzed documents"
          icon={Gauge}
          tone={avgRisk >= 50 ? "warning" : "success"}
        />
        <StatCard
          label="High-risk findings"
          value={stats.high_risk_findings}
          hint="High and critical severity"
          icon={ShieldAlert}
          tone="destructive"
        />
        <StatCard
          label="In pipeline"
          value={stats.processing}
          hint={`${stats.failed} failed`}
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
            <DonutChart data={distribution} centerLabel="documents" />
            <ul className="grid w-full grid-cols-2 gap-2">
              {RISK_LEVELS.map((level) => (
                <li key={level} className="flex items-center gap-2 text-sm">
                  <span
                    className="size-2.5 rounded-full"
                    style={{ backgroundColor: RISK_META[level].hex }}
                    aria-hidden="true"
                  />
                  <span className="text-muted-foreground">{RISK_META[level].label}</span>
                  <span className="ml-auto font-medium">
                    {stats.risk_distribution[level.toUpperCase()] ?? 0}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Findings by category</CardTitle>
          </CardHeader>
          <CardContent>
            {categories.length > 0 ? (
              <CategoryBars data={categories} />
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No categorized findings yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <RecentDocuments docs={docs} />

      <RecentActivity docs={docs} />
    </div>
  )
}

function SystemStatus() {
  const { state: health, refresh: refreshHealth } = useHealth()
  const { state: status, refresh: refreshStatus } = useStatus()

  return (
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
  )
}

export function DashboardPage() {
  const { role } = useRole()
  const statsLoader = useCallback(() => getOverviewStats(), [])
  const docsLoader = useCallback(() => listDocuments({ limit: 8 }), [])
  const { state: stats, refresh: refreshStats } = useAsync(statsLoader)
  const { state: docs, refresh: refreshDocs } = useAsync(docsLoader)

  const statsLoading = stats.phase === "loading" || stats.phase === "idle"
  const isEmpty = stats.phase === "ok" && stats.data !== null && stats.data.total_documents === 0

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {ROLE_META[role].label} workspace · Portfolio health across contracts, clauses and
            detected risk.
          </p>
        </div>
        <Button asChild>
          <Link to="/dashboard/upload">
            <Upload className="size-4" aria-hidden="true" />
            Upload document
          </Link>
        </Button>
      </div>

      {statsLoading ? (
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
      ) : isEmpty ? (
        <EmptyState
          icon={FileText}
          title="Welcome to your workspace"
          description="Upload your first contract (PDF, DOCX or TXT) to run an explainable, rule-based risk analysis."
          action={
            <Button asChild size="sm">
              <Link to="/dashboard/upload">Upload document</Link>
            </Button>
          }
        />
      ) : stats.data ? (
        <Overview
          stats={stats.data}
          docs={{
            phase: docs.phase,
            items: docs.data?.items ?? [],
            error: docs.error,
            onRetry: () => void refreshDocs(),
          }}
        />
      ) : null}

      <QuickActions actions={QUICK_ACTIONS} />

      <SystemStatus />
    </div>
  )
}
