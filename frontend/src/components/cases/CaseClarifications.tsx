import { Loader2, MessageSquare, Send } from "lucide-react"
import { useCallback, useState } from "react"

import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { useRole } from "@/context/RoleContext"
import { useAsync } from "@/hooks/useAsync"
import { ApiError } from "@/lib/api"
import { markCaseClarificationsRead, sendCaseClarification } from "@/lib/caseWorkspace"
import { formatDateTime } from "@/lib/format"
import type { CaseClarificationThread } from "@/lib/types"

function ReplyBox({
  caseId,
  thread,
  onSent,
}: {
  caseId: string
  thread: CaseClarificationThread
  onSent: () => void
}) {
  const [body, setBody] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send() {
    const text = body.trim()
    if (!text) return
    setBusy(true)
    setError(null)
    try {
      await sendCaseClarification(caseId, text, thread.lawyer_id)
      setBody("")
      onSent()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Your message could not be sent.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-2 border-t border-border pt-3">
      <Textarea
        placeholder="Write a reply…"
        value={body}
        onChange={(event) => setBody(event.target.value)}
      />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button
        className="self-end"
        size="sm"
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
  )
}

/**
 * Pre-assignment clarification thread. While a case is open, an interested
 * lawyer can ask the client for details and the client can answer. Each thread
 * is private to that lawyer and the client; other lawyers never see it.
 */
export function CaseClarifications({
  caseId,
  myDecision,
  onChanged,
}: {
  caseId: string
  myDecision: string | null
  onChanged: () => void
}) {
  const { role } = useRole()
  const isLawyer = role === "lawyer"

  const loader = useCallback(() => markCaseClarificationsRead(caseId), [caseId])
  const { state, refresh } = useAsync(loader)

  const [startBody, setStartBody] = useState("")
  const [startBusy, setStartBusy] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  const threads = state.data?.threads ?? []
  const canStartThread = isLawyer && myDecision === null && threads.length === 0

  async function startThread() {
    const text = startBody.trim()
    if (!text) return
    setStartBusy(true)
    setStartError(null)
    try {
      await sendCaseClarification(caseId, text)
      setStartBody("")
      refresh()
      onChanged()
    } catch (caught) {
      setStartError(caught instanceof ApiError ? caught.message : "Your request could not be sent.")
    } finally {
      setStartBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Clarifications</CardTitle>
        <p className="text-xs text-muted-foreground">
          Private questions and answers before a lawyer is assigned. Competing lawyers cannot see
          this thread.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {state.phase === "loading" || state.phase === "idle" ? (
          <LoadingSkeleton rows={3} />
        ) : state.phase === "error" ? (
          <ErrorState
            title="Could not load clarifications"
            description={state.error ?? undefined}
            onRetry={() => void refresh()}
          />
        ) : threads.length === 0 ? (
          canStartThread ? (
            <div className="flex flex-col gap-2">
              <Textarea
                placeholder="Ask the client for the details you need…"
                value={startBody}
                onChange={(event) => setStartBody(event.target.value)}
              />
              {startError ? <p className="text-sm text-destructive">{startError}</p> : null}
              <Button
                className="self-end"
                size="sm"
                disabled={startBusy || startBody.trim().length === 0}
                onClick={() => void startThread()}
              >
                {startBusy ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="size-4" aria-hidden="true" />
                )}
                Send question
              </Button>
            </div>
          ) : (
            <EmptyState
              icon={MessageSquare}
              title="No information requests yet"
              description="Questions a lawyer asks before being assigned will appear here."
            />
          )
        ) : (
          threads.map((thread) => (
            <div key={thread.lawyer_id} className="flex flex-col gap-3 rounded-lg border border-border p-3">
              <p className="text-sm font-medium">
                {isLawyer ? "Your information request" : (thread.lawyer_name ?? "A lawyer")}
              </p>
              <ul className="flex flex-col gap-2">
                {thread.items.map((item) => (
                  <li key={item.id} className="rounded-lg bg-muted/50 p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium">
                        {item.sender_name ?? "Unknown sender"}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatDateTime(item.created_at)}
                      </span>
                    </div>
                    <p className="mt-1 whitespace-pre-line text-sm">{item.body}</p>
                  </li>
                ))}
              </ul>
              <ReplyBox
                caseId={caseId}
                thread={thread}
                onSent={() => {
                  refresh()
                  onChanged()
                }}
              />
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}
