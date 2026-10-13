import { CheckCircle2, Inbox, Gavel, Clock3, XCircle } from "lucide-react"
import { useCallback } from "react"
import { Link } from "react-router-dom"

import { CaseTable } from "@/components/cases/CaseTable"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAsync } from "@/hooks/useAsync"
import { getMyCases } from "@/lib/cases"
import type { CaseSummary } from "@/lib/types"

type Bucket = "active" | "completed" | "pending" | "declined"

const BUCKET_META: Record<Bucket, { label: string; icon: typeof Gavel; empty: string }> = {
  active: {
    label: "Active",
    icon: Gavel,
    empty: "No active cases. Accept a case from the available list to get started.",
  },
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    empty: "You have not completed any cases yet.",
  },
  pending: {
    label: "Pending",
    icon: Clock3,
    empty: "No cases are waiting on client information.",
  },
  declined: {
    label: "Declined",
    icon: XCircle,
    empty: "You have not declined any cases.",
  },
}

function BucketTable({ bucket, cases }: { bucket: Bucket; cases: CaseSummary[] }) {
  const meta = BUCKET_META[bucket]
  const Icon = meta.icon
  return (
    <CaseTable
      cases={cases}
      empty={<EmptyState icon={Icon} title={`No ${meta.label.toLowerCase()} cases`} description={meta.empty} />}
      renderAction={(item) => (
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/dashboard/cases/${item.id}`}>Open</Link>
        </Button>
      )}
    />
  )
}

export function MyCasesPage() {
  const loader = useCallback(() => getMyCases(), [])
  const { state, refresh } = useAsync(loader)
  const loading = state.phase === "loading" || state.phase === "idle"

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">My cases</h1>
        <p className="text-sm text-muted-foreground">
          Everything you have accepted, completed, declined or are waiting on information for.
        </p>
      </div>

      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load your cases"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : state.data ? (
        <Tabs defaultValue="active">
          <TabsList className="flex-wrap">
            {(Object.keys(BUCKET_META) as Bucket[]).map((bucket) => {
              const Icon = BUCKET_META[bucket].icon
              const count = state.data?.[bucket].length ?? 0
              return (
                <TabsTrigger key={bucket} value={bucket}>
                  <Icon className="size-3.5" aria-hidden="true" />
                  {BUCKET_META[bucket].label}
                  {count > 0 ? (
                    <span className="ml-1 rounded-full bg-muted px-1.5 text-[10px] font-medium">
                      {count}
                    </span>
                  ) : null}
                </TabsTrigger>
              )
            })}
          </TabsList>

          {(Object.keys(BUCKET_META) as Bucket[]).map((bucket) => (
            <TabsContent key={bucket} value={bucket} className="mt-4">
              <BucketTable bucket={bucket} cases={state.data?.[bucket] ?? []} />
            </TabsContent>
          ))}
        </Tabs>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={Inbox}
              title="No cases yet"
              description="Once you accept a case it will appear here."
              action={
                <Button asChild size="sm">
                  <Link to="/dashboard/available-cases">Browse available cases</Link>
                </Button>
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
