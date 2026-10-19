import { useCallback, useEffect, useRef, useState } from "react"

import { ApiError, getAuthToken, websocketUrl } from "@/lib/api"
import { getCaseMessages, markCaseMessagesRead, sendCaseMessage } from "@/lib/caseWorkspace"
import { backoffDelay, mergeMessages } from "@/lib/messages"
import type { CaseMessage } from "@/lib/types"

export type ChatConnection = "connecting" | "online" | "offline"

const BASE_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 15000
const POLL_INTERVAL_MS = 5000

function describeError(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

export interface ChatController {
  messages: CaseMessage[]
  loading: boolean
  error: string | null
  connection: ChatConnection
  sending: boolean
  /** Send a message; resolves true on success so the caller can clear its input. */
  send: (body: string) => Promise<boolean>
  reload: () => void
}

/**
 * Owns the private-workspace message stream for a single case.
 *
 * History is loaded over the existing REST API; live updates arrive over a
 * WebSocket that authenticates with the stored bearer token (sent in the first
 * frame, never the URL). The socket reconnects with bounded exponential
 * backoff, and while it is down a periodic poll keeps the thread in sync — so a
 * message is never lost merely because the socket is unavailable. Incoming and
 * echoed messages are de-duplicated by id (see `mergeMessages`).
 */
export function useCaseMessages(
  caseId: string,
  currentUserId: number | null,
): ChatController {
  const [messages, setMessages] = useState<CaseMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [connection, setConnection] = useState<ChatConnection>("connecting")
  const [sending, setSending] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)

  const userIdRef = useRef<number | null>(currentUserId)
  userIdRef.current = currentUserId

  const sendingRef = useRef(false)

  const mergeIncoming = useCallback((incoming: CaseMessage[] | undefined) => {
    if (!incoming || incoming.length === 0) return
    setMessages((previous) => mergeMessages(previous, incoming))
  }, [])

  const loadHistory = useCallback(
    async (markRead: boolean) => {
      const data = markRead ? await markCaseMessagesRead(caseId) : await getCaseMessages(caseId)
      mergeIncoming(data.items)
    },
    [caseId, mergeIncoming],
  )

  const reload = useCallback(() => setReloadToken((token) => token + 1), [])

  // Initial load (and explicit reload). Marking read here also clears the
  // unread counter for this case on the server.
  useEffect(() => {
    let active = true
    setLoading(true)
    markCaseMessagesRead(caseId)
      .then((data) => {
        if (!active) return
        setMessages((previous) => mergeMessages(previous, data.items))
        setError(null)
      })
      .catch((caught) => {
        if (!active) return
        setError(describeError(caught, "Could not load messages."))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [caseId, reloadToken])

  // Live WebSocket with reconnect and polling fallback.
  useEffect(() => {
    let disposed = false
    let attempts = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let socket: WebSocket | null = null

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }

    const startPolling = () => {
      if (pollTimer || disposed) return
      pollTimer = setInterval(() => {
        void loadHistory(false).catch(() => {
          /* polling is best-effort; the next tick retries */
        })
      }, POLL_INTERVAL_MS)
    }

    const clearReconnect = () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    const scheduleReconnect = () => {
      const delay = backoffDelay(attempts, {
        baseMs: BASE_BACKOFF_MS,
        maxMs: MAX_BACKOFF_MS,
        jitter: 0.25,
      })
      attempts += 1
      clearReconnect()
      reconnectTimer = setTimeout(connect, delay)
    }

    function connect() {
      if (disposed) return
      setConnection("connecting")

      let next: WebSocket
      try {
        next = new WebSocket(websocketUrl(`/cases/${caseId}/ws`))
      } catch {
        setConnection("offline")
        startPolling()
        scheduleReconnect()
        return
      }
      socket = next

      next.onopen = () => {
        // Token travels in the first frame, not the URL, so it never lands in
        // proxy or server access logs.
        next.send(JSON.stringify({ type: "auth", token: getAuthToken() }))
      }

      next.onmessage = (event) => {
        let payload: unknown
        try {
          payload = JSON.parse(event.data as string)
        } catch {
          return
        }
        if (!payload || typeof payload !== "object") return
        const kind = (payload as { type?: unknown }).type

        if (kind === "ready") {
          attempts = 0
          setConnection("online")
          stopPolling()
          // Catch anything missed while the socket was down.
          void loadHistory(false).catch(() => {})
          return
        }

        if (kind === "message") {
          const incoming = (payload as { message?: CaseMessage }).message
          if (!incoming || typeof incoming.id !== "number") return
          mergeIncoming([incoming])
          if (incoming.sender_user_id !== userIdRef.current) {
            void markCaseMessagesRead(caseId)
              .then((data) => mergeIncoming(data.items))
              .catch(() => {})
          }
        }
      }

      next.onclose = () => {
        if (socket === next) socket = null
        if (disposed) return
        setConnection("offline")
        startPolling()
        scheduleReconnect()
      }

      next.onerror = () => {
        // `onclose` always follows; reconnect handling lives there.
      }
    }

    connect()

    return () => {
      disposed = true
      clearReconnect()
      stopPolling()
      if (socket) {
        socket.onopen = null
        socket.onmessage = null
        socket.onclose = null
        socket.onerror = null
        try {
          socket.close()
        } catch {
          /* already closing */
        }
        socket = null
      }
    }
  }, [caseId, loadHistory, mergeIncoming])

  const send = useCallback(
    async (body: string): Promise<boolean> => {
      const text = body.trim()
      // Guard against double submits before the disabled state re-renders.
      if (!text || sendingRef.current) return false
      sendingRef.current = true
      setSending(true)
      setError(null)
      try {
        const data = await sendCaseMessage(caseId, text)
        mergeIncoming(data.items)
        return true
      } catch (caught) {
        setError(describeError(caught, "Your message could not be sent."))
        return false
      } finally {
        sendingRef.current = false
        setSending(false)
      }
    },
    [caseId, mergeIncoming],
  )

  return { messages, loading, error, connection, sending, send, reload }
}
