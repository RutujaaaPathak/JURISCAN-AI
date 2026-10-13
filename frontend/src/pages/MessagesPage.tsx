import { Info, MessageSquare } from "lucide-react"
import { useCallback } from "react"
import { Link } from "react-router-dom"

import { CaseStatusBadge } from "@/components/cases/CaseBadges"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useRole } from "@/context/RoleContext"
import { useAsync } from "@/hooks/useAsync"
import { getMyCases, listCases } from "@/lib/cases"
import { formatDate } from "@/lib/format"
import type { CaseSummary } from "@/lib/types"

/**
 * Conversations are per-case and live inside each assigned case's private
 * workspace. This page is an index of the matters you can message on: the
 * lawyer's assigned cases, or the cases a client posted that have a lawyer.
 */
export function MessagesPage() {
  const { role } = useRole()

  const loader = useCallback(async (): Promise<CaseSummary[]> => {
    if (role === "lawyer") {
      const mine = await getMyCases()
      return [...mine.active, ...mine.completed]
    }
    const posted = await listCases({ limit: 100 })
    return posted.items.filter((item) => item.assigned_lawyer_id !== null)
  }, [role])

  const { state, refresh } = useAsync(loader)
  const loading = state.phase === "loading" || state.phase === "idle"
  const cases = state.data ?? []

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Messages</h1>
        <p className="text-sm text-muted-foreground">
          Conversations are private to the two parties on each matter.
        </p>
      </div>

      <Card>
        <CardContent className="flex items-start gap-3 py-1 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            There is no standalone inbox yet. Messages are exchanged inside a case, so open a
            matter below to read and reply to its conversation.
          </p>
        </CardContent>
      </Card>

      {loading ? (
        <LoadingSkeleton rows={5} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load your conversations"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : cases.length === 0 ? (
        <Card>
          <CardContent>
            <EmptyState
              icon={MessageSquare}
              title="No conversations yet"
              description={
                role === "lawyer"
                  ? "Accept a case to start messaging with a client."
                  : "Once a lawyer takes on your case, you can message them from the case workspace."
              }
              action={
                <Button asChild size="sm">
                  <Link to={role === "lawyer" ? "/dashboard/available-cases" : "/dashboard/legal-cases"}>
                    {role === "lawyer" ? "Browse available cases" : "View my legal cases"}
                  </Link>
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-1 p-2">
            <ul className="flex flex-col">
              {cases.map((item) => {
                const counterpart =
                  role === "lawyer"
                    ? (item.posted_by_name ?? "Client")
                    : (item.assigned_lawyer_name ?? "Assigned lawyer")
                return (
                  <li key={item.id}>
                    <Link
                      to={`/dashboard/cases/${item.id}`}
                      className="flex items-center gap-3 rounded-lg p-3 transition-colors hover:bg-muted/50"
                    >
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                        <MessageSquare className="size-4" aria-hidden="true" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{item.title}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {counterpart} · {formatDate(item.created_at)}
                        </p>
                      </div>
                      <CaseStatusBadge status={item.status} />
                      <span className="text-xs text-muted-foreground">Open</span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
