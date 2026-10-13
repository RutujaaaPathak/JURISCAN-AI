import {
  Activity,
  Briefcase,
  CheckCircle2,
  Gavel,
  Info,
  Inbox,
  MessageSquare,
  Settings,
  UserCog,
} from "lucide-react"
import { useCallback } from "react"
import { Link } from "react-router-dom"

import { CaseTable } from "@/components/cases/CaseTable"
import { CategoryBars, DonutChart } from "@/components/charts/Charts"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { QuickActions } from "@/components/dashboard/QuickActions"
import type { QuickAction } from "@/components/dashboard/QuickActions"
import { StatCard } from "@/components/dashboard/StatCard"
import { PageHeader } from "@/components/layout/PageHeader"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useRole } from "@/context/RoleContext"
import { useAsync } from "@/hooks/useAsync"
import { getLawyerOverview, listCases } from "@/lib/cases"
import { ROLE_META } from "@/lib/roles"
import type { LawyerOverview } from "@/lib/types"

const QUICK_ACTIONS: QuickAction[] = [
  {
    label: "Available Cases",
    description: "Browse open matters to take on",
    icon: Inbox,
    to: "/dashboard/available-cases",
  },
  {
    label: "My Cases",
    description: "Active, pending and completed work",
    icon: Gavel,
    to: "/dashboard/my-cases",
  },
  {
    label: "Lawyer Profile",
    description: "Practice details and verification",
    icon: UserCog,
    to: "/dashboard/profile",
  },
  {
    label: "Messages",
    description: "Client conversations",
    icon: MessageSquare,
    to: "/dashboard/messages",
  },
  {
    label: "Settings",
    description: "Workspace preferences",
    icon: Settings,
    to: "/dashboard/settings",
  },
]

const STATUS_COLORS: Record<string, string> = {
  ASSIGNED: "#2563eb",
  COMPLETED: "#10b981",
  CLOSED: "#6b7280",
}

const STATUS_LABELS: Record<string, string> = {
  ASSIGNED: "Active",
  COMPLETED: "Completed",
  CLOSED: "Closed",
}

function OverviewView({ overview }: { overview: LawyerOverview }) {
  const distribution = Object.entries(overview.case_status_distribution).map(([status, value]) => ({
    label: STATUS_LABELS[status] ?? status,
    value,
    color: STATUS_COLORS[status] ?? "var(--primary)",
  }))
  const categories = overview.case_category_distribution.map((entry) => ({
    label: entry.category
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" "),
    value: entry.count,
  }))

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Available cases"
          value={overview.available_cases}
          hint="Open matters matching you"
          icon={Inbox}
        />
        <StatCard
          label="Pending requests"
          value={overview.pending_requests}
          hint="Awaiting client information"
          icon={Activity}
          tone="warning"
        />
        <StatCard
          label="Active cases"
          value={overview.active_cases}
          hint="Currently assigned to you"
          icon={Briefcase}
        />
        <StatCard
          label="Completed cases"
          value={overview.completed_cases}
          hint={`${overview.total_handled} total handled`}
          icon={CheckCircle2}
          tone="success"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Your case status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-5">
            <DonutChart data={distribution} centerLabel="your cases" />
            <ul className="grid w-full grid-cols-1 gap-2">
              {distribution.map((entry) => (
                <li key={entry.label} className="flex items-center gap-2 text-sm">
                  <span
                    className="size-2.5 rounded-full"
                    style={{ backgroundColor: entry.color }}
                    aria-hidden="true"
                  />
                  <span className="text-muted-foreground">{entry.label}</span>
                  <span className="ml-auto font-medium">{entry.value}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Cases by category</CardTitle>
          </CardHeader>
          <CardContent>
            {categories.length > 0 ? (
              <CategoryBars data={categories} />
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No cases assigned or available yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export function LawyerDashboardPage() {
  const { role } = useRole()
  const overviewLoader = useCallback(() => getLawyerOverview(), [])
  const casesLoader = useCallback(() => listCases({ limit: 5, sort: "urgency" }), [])
  const { state: overview, refresh: refreshOverview } = useAsync(overviewLoader)
  const { state: cases, refresh: refreshCases } = useAsync(casesLoader)

  const loading = overview.phase === "loading" || overview.phase === "idle"

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <PageHeader
        title="Lawyer workspace"
        description={`${ROLE_META[role].label} workspace · Triage available matters and manage the cases assigned to you.`}
        actions={
          <Button asChild>
            <Link to="/dashboard/available-cases">
              <Inbox className="size-4" aria-hidden="true" />
              Browse cases
            </Link>
          </Button>
        }
      />

      <Alert variant="info">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          <AlertTitle>Sign-in and role permissions are not fully implemented</AlertTitle>
          <AlertDescription>
            Authentication does not exist yet. Cases, assignment and decisions are stored and
            enforced by the backend, but the current identity is a single demo account with a
            development-only role preview. Treat this as a scaffold, not a secure production
            workflow. Per-case messaging, fee negotiation and consultations are live inside each
            assigned case&apos;s workspace; a consolidated calendar and lawyer-verification review
            are not implemented.
          </AlertDescription>
        </div>
      </Alert>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <LoadingSkeleton key={index} rows={1} />
          ))}
        </div>
      ) : overview.phase === "error" ? (
        <ErrorState
          title="Could not load your overview"
          description={overview.error ?? undefined}
          onRetry={() => void refreshOverview()}
        />
      ) : overview.data ? (
        <OverviewView overview={overview.data} />
      ) : null}

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Most urgent open cases</CardTitle>
          <Button asChild variant="ghost" size="sm">
            <Link to="/dashboard/available-cases">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {cases.phase === "loading" || cases.phase === "idle" ? (
            <LoadingSkeleton rows={4} />
          ) : cases.phase === "error" ? (
            <ErrorState
              title="Could not load available cases"
              description={cases.error ?? undefined}
              onRetry={() => void refreshCases()}
            />
          ) : (
            <CaseTable
              cases={cases.data?.items ?? []}
              empty={
                <EmptyState
                  icon={Inbox}
                  title="No open cases right now"
                  description="New matters posted by clients will appear here for you to review."
                />
              }
              renderAction={(item) => (
                <Button variant="ghost" size="sm" asChild>
                  <Link to={`/dashboard/cases/${item.id}`}>Review</Link>
                </Button>
              )}
            />
          )}
        </CardContent>
      </Card>

      <QuickActions actions={QUICK_ACTIONS} />
    </div>
  )
}
