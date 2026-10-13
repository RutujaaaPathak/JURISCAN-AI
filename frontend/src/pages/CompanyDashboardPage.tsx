import {
  Activity,
  ArrowRight,
  ClipboardList,
  Clock3,
  FileCheck2,
  FileText,
  Gauge,
  Info,
  Settings,
  ShieldAlert,
  Upload,
} from "lucide-react"
import { useCallback } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge, StatusBadge } from "@/components/analysis/RiskBadges"
import { CategoryBars, DonutChart } from "@/components/charts/Charts"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { ActivityFeed } from "@/components/dashboard/ActivityFeed"
import { QuickActions } from "@/components/dashboard/QuickActions"
import type { QuickAction } from "@/components/dashboard/QuickActions"
import { StatCard } from "@/components/dashboard/StatCard"
import { PageHeader } from "@/components/layout/PageHeader"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
import type { AsyncPhase } from "@/hooks/useAsync"
import { buildActivity } from "@/lib/activity"
import { getOverviewStats, listDocuments } from "@/lib/documents"
import { formatFileType } from "@/lib/format"
import { RISK_LEVELS, RISK_META, riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"
import type { DocumentSummary, OverviewStats } from "@/lib/types"

const QUICK_ACTIONS: QuickAction[] = [
  {
    label: "Upload Contract",
    description: "Add a contract for review",
    icon: Upload,
    to: "/dashboard/upload",
  },
  {
    label: "Company Documents",
    description: "Browse workspace contracts",
    icon: FileText,
    to: "/dashboard/documents",
  },
  {
    label: "Analysis Reports",
    description: "Review completed analyses",
    icon: ClipboardList,
    to: "/dashboard/reports",
  },
  {
    label: "Settings",
    description: "Workspace preferences",
    icon: Settings,
    to: "/dashboard/settings",
  },
]

interface DocsView {
  phase: AsyncPhase
  items: DocumentSummary[]
  error: string | null
  onRetry: () => void
}

function RecentAnalyses({ docs }: { docs: DocsView }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Recent analyses</CardTitle>
        <Button asChild variant="ghost" size="sm">
          <Link to="/dashboard/reports">
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
            title="Could not load recent analyses"
            description={docs.error ?? undefined}
            onRetry={docs.onRetry}
          />
        ) : docs.items.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No contracts yet"
            description="Upload a contract to see its analysis appear here."
            action={
              <Button asChild size="sm">
                <Link to="/dashboard/upload">Upload contract</Link>
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
          description="Upload and analyze a contract to build an activity trail."
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
  const highRiskDocuments =
    (stats.risk_distribution["HIGH"] ?? 0) + (stats.risk_distribution["CRITICAL"] ?? 0)
  const avgRisk = Math.round(stats.avg_risk_score)

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total contracts"
          value={stats.total_documents}
          hint={`${stats.processed} analyzed`}
          icon={FileCheck2}
        />
        <StatCard
          label="Pending reviews"
          value={stats.processing}
          hint={`${stats.failed} failed`}
          icon={Clock3}
          tone="warning"
        />
        <StatCard
          label="High-risk documents"
          value={highRiskDocuments}
          hint="High and critical severity"
          icon={ShieldAlert}
          tone="destructive"
        />
        <StatCard
          label="Average risk score"
          value={avgRisk}
          hint="Across analyzed contracts"
          icon={Gauge}
          tone={avgRisk >= 50 ? "warning" : "success"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Risk distribution</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-5">
            <DonutChart data={distribution} centerLabel="contracts" />
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

      <RecentAnalyses docs={docs} />

      <RecentActivity docs={docs} />
    </div>
  )
}

export function CompanyDashboardPage() {
  const statsLoader = useCallback(() => getOverviewStats(), [])
  const docsLoader = useCallback(() => listDocuments({ limit: 8 }), [])
  const { state: stats, refresh: refreshStats } = useAsync(statsLoader)
  const { state: docs, refresh: refreshDocs } = useAsync(docsLoader)

  const statsLoading = stats.phase === "loading" || stats.phase === "idle"
  const isEmpty = stats.phase === "ok" && stats.data !== null && stats.data.total_documents === 0

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <PageHeader
        title="Company overview"
        description="Contract portfolio health across uploads, analyses and detected risk."
        actions={
          <Button asChild>
            <Link to="/dashboard/upload">
              <Upload className="size-4" aria-hidden="true" />
              Upload contract
            </Link>
          </Button>
        }
      />

      <Alert variant="info">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          <AlertTitle>Company &amp; team features are not implemented yet</AlertTitle>
          <AlertDescription>
            The backend has no organisation, team or audit-log model, so there is no separate
            company dataset. The figures below are the current workspace&apos;s real data from the
            single shared account, shown as a UI preview only — they are not scoped to a company.
            Team Management, Audit Reports and role permissions are placeholders.
          </AlertDescription>
        </div>
      </Alert>

      {statsLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <LoadingSkeleton key={index} rows={1} />
          ))}
        </div>
      ) : stats.phase === "error" ? (
        <ErrorState
          title="Could not load company overview"
          description={stats.error ?? undefined}
          onRetry={() => void refreshStats()}
        />
      ) : isEmpty ? (
        <EmptyState
          icon={FileText}
          title="No contracts yet"
          description="Upload the first contract to start building the company contract portfolio."
          action={
            <Button asChild size="sm">
              <Link to="/dashboard/upload">Upload contract</Link>
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
    </div>
  )
}
