import {
  Clock,
  History,
  Phone,
  PhoneCall,
  PhoneIncoming,
  PhoneMissed,
  PhoneOff,
} from "lucide-react"

import { EmptyState, LoadingSkeleton } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { VoiceCallController } from "@/hooks/useVoiceCall"
import { useAuth } from "@/lib/auth"
import { canStartCall, isCallInProgress } from "@/lib/callState"
import { callStatusMeta, formatCallDuration } from "@/lib/calls"
import { formatDateTime } from "@/lib/format"
import type { CaseDetail } from "@/lib/types"

interface CaseCallsTabProps {
  detail: CaseDetail
  controller: VoiceCallController
}

export function CaseCallsTab({ detail, controller }: CaseCallsTabProps) {
  const { user } = useAuth()
  const {
    callState,
    history,
    loadingHistory,
    startCall,
    endActiveCall,
    error,
    clearError,
    wsStatus,
  } = controller

  const isAssigned = detail.assigned_lawyer_id != null
  const isLawyer = user?.id === detail.assigned_lawyer_id
  const isClient = user?.id === detail.posted_by_user_id

  const canParticipate = isAssigned && (isLawyer || isClient)
  const otherPartyLabel = isLawyer
    ? (detail.posted_by_name ?? "Client")
    : (detail.assigned_lawyer_name ?? "Assigned Lawyer")

  const isInCall = isCallInProgress(callState)
  const callAvailable = canStartCall(callState) && wsStatus === "online"
  const signalingLabel =
    wsStatus === "online"
      ? "Signaling live"
      : wsStatus === "connecting"
        ? "Connecting signaling…"
        : "Signaling offline"

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Call Action Banner */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">Real-time Voice Calling</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                Direct browser-to-browser voice call over WebRTC. Audio is never stored or routed through the backend.
              </p>
              {canParticipate ? (
                <Badge
                  variant={wsStatus === "online" ? "success" : "outline"}
                  className="mt-2 text-[11px]"
                >
                  {signalingLabel}
                </Badge>
              ) : null}
            </div>
            {canParticipate ? (
              isInCall ? (
                <Button
                  variant="destructive"
                  className="gap-2"
                  onClick={() => void endActiveCall()}
                >
                  <PhoneOff className="size-4" />
                  End Call
                </Button>
              ) : (
                <Button
                  variant="default"
                  className="gap-2"
                  disabled={!callAvailable}
                  title={
                    wsStatus === "online"
                      ? undefined
                      : "Waiting for the call signaling connection."
                  }
                  onClick={() => void startCall()}
                >
                  <PhoneCall className="size-4" />
                  Call {otherPartyLabel}
                </Button>
              )
            ) : null}
          </div>
        </CardHeader>
        {!canParticipate ? (
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Voice calling is only available once a lawyer has accepted the case.
            </p>
          </CardContent>
        ) : null}
        {error ? (
          <CardContent className="pt-0">
            <div className="flex items-start justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              <span>{error}</span>
              <Button size="sm" variant="ghost" onClick={clearError}>
                Dismiss
              </Button>
            </div>
          </CardContent>
        ) : null}
      </Card>

      {/* 2. Call History */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="size-4 text-muted-foreground" />
            <CardTitle className="text-base">Call History</CardTitle>
          </div>
          <span className="text-xs text-muted-foreground">
            {history.length} {history.length === 1 ? "call" : "calls"} recorded
          </span>
        </CardHeader>
        <CardContent>
          {loadingHistory ? (
            <LoadingSkeleton rows={3} />
          ) : history.length === 0 ? (
            <EmptyState
              icon={PhoneCall}
              title="No calls yet"
              description={`You have not had any voice calls with ${otherPartyLabel} yet.`}
              action={
                canParticipate && callAvailable ? (
                  <Button size="sm" onClick={() => void startCall()}>
                    <Phone className="size-3.5 mr-1.5" />
                    Start voice call
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {history.map((call) => {
                const meta = callStatusMeta(call.status)
                const isOutgoing = call.caller_id === user?.id
                const otherParty = isOutgoing
                  ? (call.receiver_name ?? "Counsel")
                  : (call.caller_name ?? "Client")

                return (
                  <li
                    key={call.id}
                    className="flex flex-wrap items-center justify-between gap-3 p-3.5 text-sm"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted">
                        {call.status === "MISSED" ? (
                          <PhoneMissed className="size-4 text-destructive" />
                        ) : isOutgoing ? (
                          <PhoneCall className="size-4 text-primary" />
                        ) : (
                          <PhoneIncoming className="size-4 text-emerald-600" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-foreground">
                            {isOutgoing ? `Outgoing to ${otherParty}` : `Incoming from ${otherParty}`}
                          </span>
                          <Badge variant={meta.variant} className="text-[11px] py-0 px-1.5">
                            {meta.label}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {formatDateTime(call.created_at)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="size-3.5" />
                      <span>{formatCallDuration(call.duration)}</span>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

