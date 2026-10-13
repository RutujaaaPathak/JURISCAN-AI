import { Briefcase, CheckCircle2, Clock3, FileText, Gavel, Inbox, XCircle } from "lucide-react"
import { useCallback } from "react"
import { Link } from "react-router-dom"

import { CaseStatusBadge, UrgencyBadge } from "@/components/cases/CaseBadges"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAsync } from "@/hooks/useAsync"
import { listCases } from "@/lib/cases"
import { caseCategoryLabel } from "@/lib/caseFilters"
import { formatDate } from "@/lib/format"
import type { CaseSummary } from "@/lib/types"

type Bucket = "all" | "open" | "active" | "completed" | "closed"

const BUCKETS: { value: Bucket; label: string; icon: typeof Gavel }[] = [
  { value: "all", label: "All", icon: Inbox },
  { value: "open", label: "Open", icon: Clock3 },
  { value: "active", label: "Active", icon: Gavel },
  { value: "completed", label: "Completed", icon: CheckCircle2 },
  { value: "closed", label: "Closed", icon: XCircle },
]

function bucketOf(item: CaseSummary): Exclude<Bucket, "all"> {
  switch (item.status) {
    case "ASSIGNED":
      return "active"
    case "COMPLETED":
      return "completed"
    case "CLOSED":
      return "closed"
    default:
      return "open"
  }
}

function CaseRow({ item }: { item: CaseSummary }) {
  return (
    <li className="rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/dashboard/cases/${item.id}`}
            className="truncate text-sm font-medium hover:underline"
          >
            {item.title}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge variant="outline">{caseCategoryLabel(item.category)}</Badge>
            <UrgencyBadge value={item.urgency} />
            <CaseStatusBadge status={item.status} />
          </div>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to={`/dashboard/cases/${item.id}`}>Open</Link>
        </Button>
      </div>
      <dl className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
        <div>
          <dt>Posted</dt>
          <dd className="text-foreground">{formatDate(item.created_at)}</dd>
        </div>
        <div>
          <dt>Lawyer responses</dt>
          <dd className="text-foreground">{item.decision_count}</dd>
        </div>
        <div>
          <dt>Assigned lawyer</dt>
          <dd className="text-foreground">{item.assigned_lawyer_name ?? "Not assigned yet"}</dd>
        </div>
        {item.deadline ? (
          <div>
            <dt>Deadline</dt>
            <dd className="text-foreground">{formatDate(item.deadline)}</dd>
          </div>
        ) : null}
      </dl>
    </li>
  )
}

export function MyLegalCasesPage() {
  const loader = useCallback(() => listCases({ limit: 100 }), [])
  const { state, refresh } = useAsync(loader)

  const loading = state.phase === "loading" || state.phase === "idle"
  const cases = state.data?.items ?? []

  function itemsFor(bucket: Bucket): CaseSummary[] {
    if (bucket === "all") return cases
    return cases.filter((item) => bucketOf(item) === bucket)
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">My legal cases</h1>
          <p className="text-sm text-muted-foreground">
            Every matter you have posted, its status, lawyer responses and assigned lawyer.
          </p>
        </div>
        <Button asChild>
          <Link to="/dashboard/post-case">Post a case</Link>
        </Button>
      </div>

      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load your cases"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : cases.length === 0 ? (
        <Card>
          <CardContent>
            <EmptyState
              icon={Briefcase}
              title="You have not posted a case yet"
              description="Post your legal matter so eligible lawyers can review it and respond."
              action={
                <Button asChild size="sm">
                  <Link to="/dashboard/post-case">Post a case</Link>
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="all">
          <TabsList className="flex-wrap">
            {BUCKETS.map((bucket) => {
              const Icon = bucket.icon
              const count = itemsFor(bucket.value).length
              return (
                <TabsTrigger key={bucket.value} value={bucket.value}>
                  <Icon className="size-3.5" aria-hidden="true" />
                  {bucket.label}
                  {count > 0 ? (
                    <span className="ml-1 rounded-full bg-muted px-1.5 text-[10px] font-medium">
                      {count}
                    </span>
                  ) : null}
                </TabsTrigger>
              )
            })}
          </TabsList>

          {BUCKETS.map((bucket) => {
            const items = itemsFor(bucket.value)
            return (
              <TabsContent key={bucket.value} value={bucket.value} className="mt-4">
                {items.length === 0 ? (
                  <EmptyState
                    icon={FileText}
                    title={`No ${bucket.label.toLowerCase()} cases`}
                    description="Cases move between these buckets as lawyers respond and work begins."
                  />
                ) : (
                  <ul className="flex flex-col gap-3">
                    {items.map((item) => (
                      <CaseRow key={item.id} item={item} />
                    ))}
                  </ul>
                )}
              </TabsContent>
            )
          })}
        </Tabs>
      )}
    </div>
  )
}
