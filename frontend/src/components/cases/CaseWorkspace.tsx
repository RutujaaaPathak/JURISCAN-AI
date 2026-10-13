import {
  CalendarClock,
  Check,
  FilePlus2,
  FileText,
  HandCoins,
  Info,
  Loader2,
  MessageSquare,
  Send,
  X,
} from "lucide-react"
import { useCallback, useState } from "react"

import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useRole } from "@/context/RoleContext"
import { useAsync } from "@/hooks/useAsync"
import { ApiError } from "@/lib/api"
import {
  acceptCaseFee,
  cancelCaseAppointment,
  confirmCaseAppointment,
  declineCaseFee,
  getCaseAppointments,
  getCaseFees,
  markCaseMessagesRead,
  proposeCaseAppointment,
  proposeCaseFee,
  sendCaseMessage,
  shareCaseDocument,
} from "@/lib/caseWorkspace"
import { listDocuments } from "@/lib/documents"
import { formatDateTime, formatFileType } from "@/lib/format"
import type { CaseDetail } from "@/lib/types"

function feeStatusVariant(status: string): "success" | "destructive" | "warning" | "outline" {
  switch (status) {
    case "ACCEPTED":
      return "success"
    case "DECLINED":
      return "destructive"
    case "PROPOSED":
      return "warning"
    default:
      return "outline"
  }
}

function appointmentVariant(status: string): "success" | "destructive" | "warning" {
  switch (status) {
    case "CONFIRMED":
      return "success"
    case "CANCELLED":
      return "destructive"
    default:
      return "warning"
  }
}

function ActionError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
      {message}
    </p>
  )
}

function MessagesTab({ caseId }: { caseId: string }) {
  const loader = useCallback(() => markCaseMessagesRead(caseId), [caseId])
  const { state, refresh } = useAsync(loader)
  const [body, setBody] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send() {
    const text = body.trim()
    if (!text) return
    setBusy(true)
    setError(null)
    try {
      await sendCaseMessage(caseId, text)
      setBody("")
      refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Your message could not be sent.")
    } finally {
      setBusy(false)
    }
  }

  const items = state.data?.items ?? []

  return (
    <div className="flex flex-col gap-4">
      {state.phase === "loading" || state.phase === "idle" ? (
        <LoadingSkeleton rows={4} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load messages"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="No messages yet"
          description="Start the conversation to coordinate on this matter."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((message) => (
            <li key={message.id} className="rounded-lg border border-border p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">
                  {message.sender_name ?? "Unknown sender"}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatDateTime(message.created_at)}
                </span>
              </div>
              <p className="mt-1 whitespace-pre-line text-sm">{message.body}</p>
            </li>
          ))}
        </ul>
      )}

      <ActionError message={error} />

      <div className="flex flex-col gap-2">
        <Textarea
          placeholder="Write a message…"
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        <Button
          className="self-end"
          disabled={busy || body.trim().length === 0}
          onClick={() => void send()}
        >
          {busy ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="size-4" aria-hidden="true" />
          )}
          Send
        </Button>
      </div>
    </div>
  )
}

function DocumentsTab({
  caseId,
  detail,
  canAttach,
  onChanged,
}: {
  caseId: string
  detail: CaseDetail
  canAttach: boolean
  onChanged: () => void
}) {
  const docsLoader = useCallback(() => listDocuments({ limit: 50 }), [])
  const { state: docsState } = useAsync(docsLoader)
  const [choice, setChoice] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const attachedIds = new Set(detail.documents.map((doc) => doc.document_id))
  const available = (docsState.data?.items ?? []).filter((doc) => !attachedIds.has(doc.id))

  async function attach() {
    const documentId = Number(choice)
    if (!documentId) return
    setBusy(true)
    setError(null)
    try {
      await shareCaseDocument(caseId, documentId)
      setChoice("")
      onChanged()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The document could not be shared.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {detail.documents.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No shared documents"
          description="Documents you share here are visible only to the two parties on this case."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {detail.documents.map((document) => (
            <li
              key={document.id}
              className="flex items-center gap-3 rounded-lg border border-border p-3"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{document.title}</p>
                <p className="truncate text-xs text-muted-foreground">{document.filename}</p>
              </div>
              <Badge variant="outline">{formatFileType(document.file_type)}</Badge>
            </li>
          ))}
        </ul>
      )}

      {canAttach ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Share a document</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <ActionError message={error} />
            {docsState.phase === "loading" || docsState.phase === "idle" ? (
              <LoadingSkeleton rows={2} />
            ) : available.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                All of your processed documents are already attached to this case.
              </p>
            ) : (
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label htmlFor="share-doc">Your document</Label>
                  <Select
                    id="share-doc"
                    value={choice}
                    onChange={(event) => setChoice(event.target.value)}
                  >
                    <option value="">Select a document…</option>
                    {available.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.title}
                      </option>
                    ))}
                  </Select>
                </div>
                <Button disabled={busy || !choice} onClick={() => void attach()}>
                  <FilePlus2 className="size-4" aria-hidden="true" />
                  Share
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function FeesTab({ caseId }: { caseId: string }) {
  const loader = useCallback(() => getCaseFees(caseId), [caseId])
  const { state, refresh } = useAsync(loader)
  const [amount, setAmount] = useState("")
  const [currency, setCurrency] = useState("INR")
  const [note, setNote] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The action could not be completed.")
    } finally {
      setBusy(false)
    }
  }

  async function propose() {
    if (!amount.trim()) return
    await run(async () => {
      await proposeCaseFee(caseId, { amount: amount.trim(), currency, note: note.trim() || null })
      setAmount("")
      setNote("")
    })
  }

  const fees = state.data ?? []
  const open = fees.find((fee) => fee.status === "PROPOSED")

  return (
    <div className="flex flex-col gap-4">
      {open ? (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            An open proposal of {open.currency} {open.amount} from{" "}
            {open.proposed_by_name ?? "the other party"} is awaiting a response. Proposing a new fee
            supersedes it.
          </p>
        </div>
      ) : null}

      <ActionError message={error} />

      {state.phase === "loading" || state.phase === "idle" ? (
        <LoadingSkeleton rows={3} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load fee proposals"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : fees.length === 0 ? (
        <EmptyState
          icon={HandCoins}
          title="No fee proposals yet"
          description="Propose a fee or counteroffer to agree on costs for this matter."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {fees.map((fee) => (
            <li key={fee.id} className="rounded-lg border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium">
                  {fee.currency} {fee.amount}
                </span>
                <Badge variant={feeStatusVariant(fee.status)}>{fee.status}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Proposed by {fee.proposed_by_name ?? "someone"} ·{" "}
                {formatDateTime(fee.created_at)}
              </p>
              {fee.note ? <p className="mt-1 text-sm">{fee.note}</p> : null}
              {fee.status === "PROPOSED" ? (
                <div className="mt-2 flex gap-2">
                  <Button
                    size="sm"
                    disabled={busy}
                    onClick={() => void run(() => acceptCaseFee(caseId, fee.id))}
                  >
                    <Check className="size-4" aria-hidden="true" />
                    Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void run(() => declineCaseFee(caseId, fee.id))}
                  >
                    <X className="size-4" aria-hidden="true" />
                    Decline
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Propose a fee</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fee-amount">Amount</Label>
              <Input
                id="fee-amount"
                inputMode="decimal"
                placeholder="e.g. 15000"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fee-currency">Currency</Label>
              <Select
                id="fee-currency"
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
              >
                {["INR", "USD", "EUR", "GBP"].map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fee-note">Note (optional)</Label>
            <Textarea
              id="fee-note"
              placeholder="What the fee covers"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </div>
          <Button
            className="self-end"
            disabled={busy || amount.trim().length === 0}
            onClick={() => void propose()}
          >
            Propose fee
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function ConsultationsTab({ caseId }: { caseId: string }) {
  const loader = useCallback(() => getCaseAppointments(caseId), [caseId])
  const { state, refresh } = useAsync(loader)
  const [scheduledAt, setScheduledAt] = useState("")
  const [duration, setDuration] = useState("30")
  const [mode, setMode] = useState("video")
  const [location, setLocation] = useState("")
  const [notes, setNotes] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The action could not be completed.")
    } finally {
      setBusy(false)
    }
  }

  async function propose() {
    if (!scheduledAt) return
    await run(async () => {
      await proposeCaseAppointment(caseId, {
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: Number(duration) || null,
        mode,
        location: location.trim() || null,
        notes: notes.trim() || null,
      })
      setScheduledAt("")
      setLocation("")
      setNotes("")
    })
  }

  const appointments = state.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <ActionError message={error} />

      {state.phase === "loading" || state.phase === "idle" ? (
        <LoadingSkeleton rows={3} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load consultations"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : appointments.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title="No consultations scheduled"
          description="Propose a time to consult on this matter."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {appointments.map((appointment) => (
            <li key={appointment.id} className="rounded-lg border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium">
                  {formatDateTime(appointment.scheduled_at)}
                  {appointment.duration_minutes ? ` · ${appointment.duration_minutes} min` : ""}
                </span>
                <Badge variant={appointmentVariant(appointment.status)}>
                  {appointment.status}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Proposed by {appointment.proposed_by_name ?? "someone"}
                {appointment.mode ? ` · ${appointment.mode}` : ""}
                {appointment.location ? ` · ${appointment.location}` : ""}
              </p>
              {appointment.notes ? <p className="mt-1 text-sm">{appointment.notes}</p> : null}
              {appointment.status !== "CANCELLED" ? (
                <div className="mt-2 flex gap-2">
                  {appointment.status === "PROPOSED" ? (
                    <Button
                      size="sm"
                      disabled={busy}
                      onClick={() => void run(() => confirmCaseAppointment(caseId, appointment.id))}
                    >
                      <Check className="size-4" aria-hidden="true" />
                      Confirm
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void run(() => cancelCaseAppointment(caseId, appointment.id))}
                  >
                    <X className="size-4" aria-hidden="true" />
                    Cancel
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Propose a consultation</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="appt-time">Date and time</Label>
              <Input
                id="appt-time"
                type="datetime-local"
                value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="appt-duration">Duration (minutes)</Label>
              <Input
                id="appt-duration"
                inputMode="numeric"
                value={duration}
                onChange={(event) => setDuration(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="appt-mode">Mode</Label>
              <Select
                id="appt-mode"
                value={mode}
                onChange={(event) => setMode(event.target.value)}
              >
                <option value="video">Video call</option>
                <option value="phone">Phone</option>
                <option value="in-person">In person</option>
                <option value="chat">Chat</option>
              </Select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="appt-location">Location (optional)</Label>
            <Input
              id="appt-location"
              placeholder="Address or meeting link"
              value={location}
              onChange={(event) => setLocation(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="appt-notes">Agenda (optional)</Label>
            <Textarea
              id="appt-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </div>
          <Button
            className="self-end"
            disabled={busy || !scheduledAt}
            onClick={() => void propose()}
          >
            Propose time
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * Private workspace shared by the two parties of an assigned case. The client
 * can attach their own documents; both parties can message, negotiate fees and
 * schedule consultations. Access is enforced server-side.
 */
export function CaseWorkspace({
  caseId,
  detail,
  onChanged,
}: {
  caseId: string
  detail: CaseDetail
  onChanged: () => void
}) {
  const { role } = useRole()
  const canAttach = role !== "lawyer"

  return (
    <Card>
      <CardHeader>
        <CardTitle>Private workspace</CardTitle>
        <p className="text-xs text-muted-foreground">
          Visible only to you and the other party on this case.
        </p>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="messages">
          <TabsList className="flex-wrap">
            <TabsTrigger value="messages">
              <MessageSquare className="size-3.5" aria-hidden="true" />
              Messages
            </TabsTrigger>
            <TabsTrigger value="documents">
              <FileText className="size-3.5" aria-hidden="true" />
              Documents
            </TabsTrigger>
            <TabsTrigger value="fees">
              <HandCoins className="size-3.5" aria-hidden="true" />
              Fees
            </TabsTrigger>
            <TabsTrigger value="consultations">
              <CalendarClock className="size-3.5" aria-hidden="true" />
              Consultations
            </TabsTrigger>
          </TabsList>

          <TabsContent value="messages" className="mt-4">
            <MessagesTab caseId={caseId} />
          </TabsContent>
          <TabsContent value="documents" className="mt-4">
            <DocumentsTab
              caseId={caseId}
              detail={detail}
              canAttach={canAttach}
              onChanged={onChanged}
            />
          </TabsContent>
          <TabsContent value="fees" className="mt-4">
            <FeesTab caseId={caseId} />
          </TabsContent>
          <TabsContent value="consultations" className="mt-4">
            <ConsultationsTab caseId={caseId} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
