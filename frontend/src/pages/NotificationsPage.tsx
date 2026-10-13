import {
  Bell,
  CalendarClock,
  CheckCircle2,
  FileText,
  Gavel,
  HandCoins,
  MessageSquare,
  XCircle,
} from "lucide-react"
import { useCallback } from "react"
import type { LucideIcon } from "lucide-react"
import { Link } from "react-router-dom"

import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useAsync } from "@/hooks/useAsync"
import { getNotifications } from "@/lib/caseWorkspace"
import { formatDateTime } from "@/lib/format"
import type { NotificationItem } from "@/lib/types"

// Keys must match the `kind` values the backend emits (case activity action
// names plus "MESSAGE"), otherwise every item falls back to the Bell icon.
const KIND_ICON: Record<string, LucideIcon> = {
  CREATED: FileText,
  ACCEPTED: Gavel,
  DECLINED: XCircle,
  INFO_REQUESTED: MessageSquare,
  COMPLETED: CheckCircle2,
  DOCUMENT_SHARED: FileText,
  FEE_PROPOSED: HandCoins,
  FEE_ACCEPTED: HandCoins,
  FEE_DECLINED: HandCoins,
  APPOINTMENT_PROPOSED: CalendarClock,
  APPOINTMENT_CONFIRMED: CalendarClock,
  APPOINTMENT_CANCELLED: CalendarClock,
  MESSAGE: MessageSquare,
}

export function NotificationsPage() {
  const loader = useCallback(() => getNotifications(), [])
  const { state, refresh } = useAsync(loader)
  const loading = state.phase === "loading" || state.phase === "idle"
  const items = state.data ?? []

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          Case updates derived from your own matters and unread messages.
        </p>
      </div>

      <p className="rounded-lg border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
        These updates are generated on request from your case activity. They are not pushed or
        emailed, and there is no mark-as-read state.
      </p>

      {loading ? (
        <LoadingSkeleton rows={5} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load notifications"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="You're all caught up"
          description="Updates about your cases and messages will appear here."
        />
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-1 p-2">
            <ul className="flex flex-col">
              {items.map((item: NotificationItem) => {
                const Icon = KIND_ICON[item.kind] ?? Bell
                const body = (
                  <div className="flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-muted/50">
                    <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{item.title}</p>
                      {item.detail ? (
                        <p className="text-sm text-muted-foreground">{item.detail}</p>
                      ) : null}
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {formatDateTime(item.created_at)}
                      </p>
                    </div>
                  </div>
                )
                return (
                  <li key={item.id}>
                    {item.case_id ? (
                      <Link to={`/dashboard/cases/${item.case_id}`} className="block">
                        {body}
                      </Link>
                    ) : (
                      body
                    )}
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      <Button variant="outline" size="sm" className="self-start" onClick={() => void refresh()}>
        Refresh
      </Button>
    </div>
  )
}
