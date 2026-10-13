import {
  ArrowLeft,
  Building2,
  Check,
  CheckCircle2,
  Clock3,
  FilePlus2,
  FileText,
  Info,
  MessageSquare,
  Paperclip,
  ShieldCheck,
  User,
  X,
  XCircle,
} from "lucide-react"
import { useCallback, useState } from "react"
import type { LucideIcon } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { StatusBadge } from "@/components/analysis/RiskBadges"
import { CaseStatusBadge, DecisionBadge, UrgencyBadge } from "@/components/cases/CaseBadges"
import { CaseClarifications } from "@/components/cases/CaseClarifications"
import { CaseWorkspace } from "@/components/cases/CaseWorkspace"
import { ActivityFeed } from "@/components/dashboard/ActivityFeed"
import type { ActivityItem } from "@/components/dashboard/ActivityFeed"
import { ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useRole } from "@/context/RoleContext"
import { useAsync } from "@/hooks/useAsync"
import { ApiError } from "@/lib/api"
import { acceptCase, addCaseNote, completeCase, getCase, rejectCase, requestCaseInfo } from "@/lib/cases"
import { caseCategoryLabel } from "@/lib/caseFilters"
import { formatDateTime } from "@/lib/format"
import type { CaseActivityRead } from "@/lib/types"

const ACTION_META: Record<string, { icon: LucideIcon; tone: ActivityItem["tone"] }> = {
  CREATED: { icon: FilePlus2, tone: "default" },
  ACCEPTED: { icon: Check, tone: "success" },
  DECLINED: { icon: XCircle, tone: "destructive" },
  INFO_REQUESTED: { icon: MessageSquare, tone: "warning" },
  COMPLETED: { icon: CheckCircle2, tone: "success" },
}

type DialogKind = "accept" | "decline" | "request" | "complete"

function MetaRow({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2 text-sm">
      <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="text-muted-foreground">{label}</span>
      <span className="ml-auto text-right font-medium">{value}</span>
    </div>
  )
}

function buildActivities(activities: CaseActivityRead[]): ActivityItem[] {
  return activities.map((activity) => {
    const meta = ACTION_META[activity.action] ?? { icon: Info, tone: "default" as const }
    return {
      id: String(activity.id),
      title: activity.detail ?? activity.action,
      description: activity.actor_name ?? undefined,
      timestamp: activity.created_at,
      icon: meta.icon,
      tone: meta.tone,
    }
  })
}

export function CaseDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { role } = useRole()
  const caseId = id ?? ""

  const loader = useCallback(() => getCase(caseId), [caseId])
  const { state, refresh } = useAsync(loader)

  const [dialog, setDialog] = useState<DialogKind | null>(null)
  const [reason, setReason] = useState("")
  const [message, setMessage] = useState("")
  const [note, setNote] = useState("")
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const detail = state.data
  const isLawyer = role === "lawyer"
  const isAssigned = detail?.my_decision === "ACCEPT" && detail?.assigned_lawyer_id != null
  // A lawyer may still accept or decline after requesting more information; only
  // an existing accept/reject decision locks them out.
  const canAcceptOrDecline =
    isLawyer &&
    detail?.status === "OPEN" &&
    detail?.my_decision !== "ACCEPT" &&
    detail?.my_decision !== "REJECT" &&
    !isAssigned
  const canRequestInfo = canAcceptOrDecline && detail?.my_decision === null
  // Only parties see the full decision history and activity trail; browsing
  // lawyers see neither (the API returns empty lists for them).
  const seesDecisions = !isLawyer || isAssigned

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    try {
      await action()
      setDialog(null)
      setReason("")
      setMessage("")
      setNote("")
      refresh()
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "The action could not be completed.")
    } finally {
      setBusy(false)
    }
  }

  if (state.phase === "loading" || state.phase === "idle") {
    return (
      <div className="mx-auto w-full max-w-5xl">
        <LoadingSkeleton rows={6} />
      </div>
    )
  }

  if (state.phase === "error" || !detail) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        <ErrorState
          title="Case unavailable"
          description={state.error ?? "This case could not be loaded."}
          onRetry={() => void refresh()}
        />
        <Button variant="outline" className="self-start" onClick={() => navigate(-1)}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          Go back
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-3">
        <Button variant="ghost" size="sm" className="self-start" asChild>
          <Link to={isLawyer ? "/dashboard/my-cases" : "/dashboard/legal-cases"}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back to cases
          </Link>
        </Button>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{detail.title}</h1>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{caseCategoryLabel(detail.category)}</Badge>
              <UrgencyBadge value={detail.urgency} />
              <CaseStatusBadge status={detail.status} />
              <DecisionBadge decision={detail.my_decision} />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {canAcceptOrDecline ? (
              <>
                <Button onClick={() => setDialog("accept")}>
                  <Check className="size-4" aria-hidden="true" />
                  Accept case
                </Button>
                {canRequestInfo ? (
                  <Button variant="outline" onClick={() => setDialog("request")}>
                    <MessageSquare className="size-4" aria-hidden="true" />
                    Request info
                  </Button>
                ) : null}
                <Button variant="destructive" onClick={() => setDialog("decline")}>
                  <X className="size-4" aria-hidden="true" />
                  Decline
                </Button>
              </>
            ) : null}
            {isAssigned && detail.status === "ASSIGNED" ? (
              <Button onClick={() => setDialog("complete")}>
                <CheckCircle2 className="size-4" aria-hidden="true" />
                Mark completed
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      {actionError ? (
        <Alert variant="destructive">
          <AlertTitle>Action failed</AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      ) : null}

      {detail.assigned_lawyer_name ? (
        <Alert variant="success">
          <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div>
            <AlertTitle>Case accepted</AlertTitle>
            <AlertDescription>
              {detail.assigned_lawyer_name} is handling this matter
              {detail.accepted_at ? ` since ${formatDateTime(detail.accepted_at)}` : ""}.
            </AlertDescription>
          </div>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Case summary</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="whitespace-pre-line text-sm text-muted-foreground">{detail.summary}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <MetaRow
                icon={User}
                label="Posted by"
                value={detail.posted_by_name ?? "Client"}
              />
              <MetaRow
                icon={Building2}
                label="Jurisdiction"
                value={detail.jurisdiction ?? "Not specified"}
              />
              <MetaRow
                icon={Clock3}
                label="Posted"
                value={formatDateTime(detail.created_at)}
              />
              <MetaRow
                icon={MessageSquare}
                label="Consultation"
                value={detail.consultation_method ?? "Not specified"}
              />
              {detail.deadline ? (
                <MetaRow
                  icon={Clock3}
                  label="Deadline"
                  value={formatDateTime(detail.deadline)}
                />
              ) : null}
            </div>
            {detail.budget || detail.contact_preference || detail.client_reference ? (
              <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-2">
                {detail.budget ? (
                  <MetaRow icon={FileText} label="Budget" value={detail.budget} />
                ) : null}
                {detail.contact_preference ? (
                  <MetaRow
                    icon={MessageSquare}
                    label="Contact"
                    value={detail.contact_preference}
                  />
                ) : null}
                {detail.client_reference ? (
                  <MetaRow
                    icon={FileText}
                    label="Reference"
                    value={detail.client_reference}
                  />
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Attached documents</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {detail.documents.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No documents were attached to this case.
              </p>
            ) : (
              detail.documents.map((document) => (
                <div
                  key={document.id}
                  className="flex items-center gap-2 rounded-lg border border-border p-2.5"
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                    <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{document.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{document.filename}</p>
                  </div>
                  {document.status === "PROCESSED" ? (
                    <Button variant="ghost" size="sm" asChild>
                      <Link to={`/dashboard/analyses/${document.document_id}`}>Open</Link>
                    </Button>
                  ) : (
                    <StatusBadge status={document.status} />
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Decision history</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {!seesDecisions ? (
              <p className="text-sm text-muted-foreground">
                Decision history and rejection reasons are private to the case&apos;s client and
                assigned lawyer. Your own request appears under Clarifications.
              </p>
            ) : detail.decisions.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No lawyer has acted on this case yet.
              </p>
            ) : (
              detail.decisions.map((decision) => (
                <div key={decision.id} className="rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <DecisionBadge decision={decision.decision} />
                    <span className="text-xs text-muted-foreground">
                      {formatDateTime(decision.created_at)}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {decision.lawyer_name ?? "A lawyer"}
                  </p>
                  {decision.reason ? (
                    <p className="mt-1 text-sm">
                      <span className="text-muted-foreground">Reason: </span>
                      {decision.reason}
                    </p>
                  ) : null}
                  {decision.message ? (
                    <p className="mt-1 text-sm">
                      <span className="text-muted-foreground">Message: </span>
                      {decision.message}
                    </p>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <ActivityFeed
          items={buildActivities(detail.activities)}
          empty={
            !seesDecisions ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Activity on this case is private until a lawyer is assigned to you.
              </p>
            ) : undefined
          }
        />
      </div>

      {detail.assigned_lawyer_id == null ? (
        <CaseClarifications
          caseId={caseId}
          myDecision={detail.my_decision}
          onChanged={() => refresh()}
        />
      ) : (
        <CaseWorkspace caseId={caseId} detail={detail} onChanged={() => refresh()} />
      )}

      {isAssigned ? (
        <Card>
          <CardHeader>
            <CardTitle>Private notes</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Info className="size-3.5" aria-hidden="true" />
              Only you can see these notes. They are never shared with the client.
            </p>
            {detail.notes.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {detail.notes.map((entry) => (
                  <li key={entry.id} className="rounded-lg border border-border p-3 text-sm">
                    <p className="whitespace-pre-line">{entry.body}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatDateTime(entry.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No notes yet.</p>
            )}
            <Textarea
              placeholder="Add a private working note…"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <Button
              className="self-start"
              disabled={busy || note.trim().length === 0}
              onClick={() => void run(() => addCaseNote(caseId, note.trim()))}
            >
              <Paperclip className="size-4" aria-hidden="true" />
              Add note
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <Dialog open={dialog === "accept"} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Accept this case?</DialogTitle>
            <DialogDescription>
              You will become the assigned lawyer for “{detail.title}”. Only one lawyer can accept
              a case, and other lawyers will no longer see it as available.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={busy}>
                Cancel
              </Button>
            </DialogClose>
            <Button disabled={busy} onClick={() => void run(() => acceptCase(caseId))}>
              <Check className="size-4" aria-hidden="true" />
              Confirm acceptance
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialog === "request"} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request more information</DialogTitle>
            <DialogDescription>
              Ask the client for the details you need. The case stays open while you wait.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="request-message">Message</Label>
            <Textarea
              id="request-message"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="What information do you need?"
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={busy}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              disabled={busy || message.trim().length === 0}
              onClick={() => void run(() => requestCaseInfo(caseId, message.trim()))}
            >
              Send request
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialog === "decline"} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Decline this case</DialogTitle>
            <DialogDescription>
              Give a brief reason. The case remains available to other lawyers.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="decline-reason">Reason</Label>
            <Textarea
              id="decline-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="e.g. Outside my practice area"
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={busy}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={busy || reason.trim().length === 0}
              onClick={() => void run(() => rejectCase(caseId, reason.trim()))}
            >
              Decline case
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialog === "complete"} onOpenChange={(open) => !open && setDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mark case completed?</DialogTitle>
            <DialogDescription>
              This closes out the matter from your active list. You can still view it afterwards.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={busy}>
                Cancel
              </Button>
            </DialogClose>
            <Button disabled={busy} onClick={() => void run(() => completeCase(caseId))}>
              <CheckCircle2 className="size-4" aria-hidden="true" />
              Mark completed
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
