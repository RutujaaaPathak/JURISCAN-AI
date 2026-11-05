import { useCallback, useEffect, useRef, useState } from "react"
import type { RefObject } from "react"

import { ApiError, getAuthToken, websocketUrl } from "@/lib/api"
import type { AuthUser } from "@/lib/auth"
import {
  canAcceptIncomingCall,
  canRejectIncomingCall,
  canStartCall,
  connectionStateUpdate,
  incomingCallDecision,
  isCallInProgress,
  RING_TIMEOUT_MS,
  shouldQueueIceCandidate,
  toggleTrackMute,
} from "@/lib/callState"
import {
  acceptCall,
  endCall,
  getActiveCall,
  getCallHistory,
  getIceServers,
  initiateCall,
  rejectCall,
} from "@/lib/calls"
import { backoffDelay } from "@/lib/messages"
import type { CallRead, CallState } from "@/lib/types"

export type CallWsStatus = "connecting" | "online" | "offline"

const BASE_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 10000
const PING_INTERVAL_MS = 25000
const SETUP_TIMEOUT_MS = 30_000

export interface VoiceCallController {
  activeCall: CallRead | null
  incomingCall: CallRead | null
  callState: CallState
  isMuted: boolean
  duration: number
  remoteAudioRef: RefObject<HTMLAudioElement | null>
  error: string | null
  history: CallRead[]
  loadingHistory: boolean
  wsStatus: CallWsStatus
  startCall: () => Promise<boolean>
  acceptIncomingCall: () => Promise<boolean>
  rejectIncomingCall: (reason?: string) => Promise<boolean>
  endActiveCall: (reason?: string) => Promise<boolean>
  toggleMute: () => void
  reloadHistory: () => void
  clearError: () => void
}

function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error && error.message) return error.message
  return fallback
}

function isWebSocketOpen(socket: WebSocket | null): socket is WebSocket {
  return socket !== null && socket.readyState === WebSocket.OPEN
}

export function useVoiceCall(
  caseId: string,
  currentUser: AuthUser | null,
  enabled = true,
): VoiceCallController {
  const [activeCall, setActiveCall] = useState<CallRead | null>(null)
  const [incomingCall, setIncomingCall] = useState<CallRead | null>(null)
  const [callState, setCallState] = useState<CallState>("idle")
  const [isMuted, setIsMuted] = useState(false)
  const [duration, setDuration] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<CallRead[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [wsStatus, setWsStatus] = useState<CallWsStatus>("connecting")

  const pcRef = useRef<RTCPeerConnection | null>(null)
  const localStreamRef = useRef<MediaStream | null>(null)
  const remoteStreamRef = useRef<MediaStream | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const pendingIceCandidatesRef = useRef<RTCIceCandidateInit[]>([])
  const pendingOfferRef = useRef<RTCSessionDescriptionInit | null>(null)
  const applyingOfferRef = useRef(false)
  const remoteAudioRef = useRef<HTMLAudioElement | null>(null)
  const durationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const ringTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const setupTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const localTerminalCallRef = useRef<number | null>(null)

  const currentUserRef = useRef<AuthUser | null>(currentUser)
  currentUserRef.current = currentUser

  const callStateRef = useRef<CallState>(callState)
  const activeCallRef = useRef<CallRead | null>(activeCall)
  const incomingCallRef = useRef<CallRead | null>(incomingCall)

  const updateCallState = useCallback((next: CallState) => {
    callStateRef.current = next
    setCallState(next)
  }, [])

  const updateActiveCall = useCallback((call: CallRead | null) => {
    activeCallRef.current = call
    setActiveCall(call)
  }, [])

  const updateIncomingCall = useCallback((call: CallRead | null) => {
    incomingCallRef.current = call
    setIncomingCall(call)
  }, [])

  const clearDurationTimer = useCallback(() => {
    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current)
      durationTimerRef.current = null
    }
  }, [])

  const clearRingTimeout = useCallback(() => {
    if (ringTimeoutRef.current) {
      clearTimeout(ringTimeoutRef.current)
      ringTimeoutRef.current = null
    }
  }, [])

  const clearSetupTimeout = useCallback(() => {
    if (setupTimeoutRef.current) {
      clearTimeout(setupTimeoutRef.current)
      setupTimeoutRef.current = null
    }
  }, [])

  const cleanupPeerConnection = useCallback(() => {
    clearDurationTimer()
    clearRingTimeout()
    clearSetupTimeout()

    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop())
      localStreamRef.current = null
    }

    if (pcRef.current) {
      pcRef.current.onicecandidate = null
      pcRef.current.ontrack = null
      pcRef.current.onconnectionstatechange = null
      pcRef.current.close()
      pcRef.current = null
    }

    pendingIceCandidatesRef.current = []
    pendingOfferRef.current = null
    applyingOfferRef.current = false
    remoteStreamRef.current = null

    if (remoteAudioRef.current) {
      remoteAudioRef.current.pause()
      remoteAudioRef.current.srcObject = null
    }

    setIsMuted(false)
  }, [clearDurationTimer, clearRingTimeout, clearSetupTimeout])

  const reloadHistory = useCallback(() => {
    if (!enabled || !caseId) {
      setHistory([])
      setLoadingHistory(false)
      return
    }
    setLoadingHistory(true)
    getCallHistory(caseId, 20)
      .then((data) => {
        setHistory(data.items)
      })
      .catch(() => {
        /* best-effort history load */
      })
      .finally(() => {
        setLoadingHistory(false)
      })
  }, [caseId, enabled])

  useEffect(() => {
    reloadHistory()
  }, [reloadHistory])

  useEffect(() => {
    if (callState === "connected") {
      setDuration(0)
      durationTimerRef.current = setInterval(() => {
        setDuration((previous) => previous + 1)
      }, 1000)
    } else {
      clearDurationTimer()
    }
    return () => {
      clearDurationTimer()
    }
  }, [callState, clearDurationTimer])

  // Ensure the remote stream is attached once the <audio> element is mounted.
  useEffect(() => {
    const audio = remoteAudioRef.current
    const stream = remoteStreamRef.current
    if (!audio || !stream) return
    if (audio.srcObject !== stream) audio.srcObject = stream
    void audio.play().catch(() => {
      /* Autoplay may need a user gesture; controls still work. */
    })
  }, [callState])

  const drainPendingIceCandidates = useCallback(async (pc: RTCPeerConnection) => {
    const queue = [...pendingIceCandidatesRef.current]
    pendingIceCandidatesRef.current = []
    for (const candidate of queue) {
      try {
        await pc.addIceCandidate(new RTCIceCandidate(candidate))
      } catch {
        /* candidate may be stale */
      }
    }
  }, [])

  const getMicrophoneStream = useCallback(async (): Promise<MediaStream> => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      throw new Error("WebRTC voice calling is not supported in this browser.")
    }

    updateCallState("requesting_permission")
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      })
      localStreamRef.current = stream
      setIsMuted(false)
      return stream
    } catch (caught: unknown) {
      const name = (caught as { name?: string })?.name
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        throw new Error(
          "Microphone permission was denied. Please allow microphone access in your browser settings.",
        )
      }
      if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        throw new Error("No microphone was found on this device.")
      }
      throw new Error("Could not access the microphone.")
    }
  }, [updateCallState])

  const sendSignal = useCallback((payload: Record<string, unknown>): boolean => {
    const socket = socketRef.current
    if (!isWebSocketOpen(socket)) return false
    try {
      socket.send(JSON.stringify(payload))
      return true
    } catch {
      return false
    }
  }, [])

  const applyPendingOffer = useCallback(
    async (pc: RTCPeerConnection, callId: number) => {
      const offer = pendingOfferRef.current
      if (!offer || applyingOfferRef.current) return
      if (pc.signalingState === "closed" || pc.remoteDescription) {
        pendingOfferRef.current = null
        return
      }

      applyingOfferRef.current = true
      try {
        await pc.setRemoteDescription(new RTCSessionDescription(offer))
        pendingOfferRef.current = null
        await drainPendingIceCandidates(pc)

        const answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        if (!sendSignal({ type: "answer", call_id: callId, sdp: answer })) {
          setError("The signaling connection closed before the call could be answered.")
        }
      } catch {
        setError("The call could not be established.")
      } finally {
        applyingOfferRef.current = false
      }
    },
    [drainPendingIceCandidates, sendSignal],
  )

  const scheduleRingTimeout = useCallback(
    (callId: number) => {
      clearRingTimeout()
      ringTimeoutRef.current = setTimeout(() => {
        void (async () => {
          try {
            const response = await getActiveCall(caseId)
            const active = response.active_call
            // Reading the active call also lets the backend transition a stale
            // ringing call to MISSED. If it is somehow still ringing, end it.
            if (active && active.id === callId && active.status === "RINGING") {
              await endCall(caseId, callId, "no_answer").catch(() => {})
            }
          } catch {
            /* best effort */
          }

          const state = callStateRef.current
          if (
            activeCallRef.current?.id === callId &&
            (state === "calling" || state === "ringing")
          ) {
            cleanupPeerConnection()
            updateActiveCall(null)
            updateIncomingCall(null)
            updateCallState("ended")
            setError("No answer. The call was missed.")
            reloadHistory()
          }
        })()
      }, RING_TIMEOUT_MS + 1000)
    },
    [
      caseId,
      cleanupPeerConnection,
      clearRingTimeout,
      reloadHistory,
      updateActiveCall,
      updateCallState,
      updateIncomingCall,
    ],
  )

  const scheduleSetupTimeout = useCallback(
    (callId: number) => {
      clearSetupTimeout()
      setupTimeoutRef.current = setTimeout(() => {
        if (callStateRef.current === "connected") return
        if (activeCallRef.current?.id !== callId) return

        void endCall(caseId, callId, "connection_timeout").catch(() => {})
        cleanupPeerConnection()
        updateActiveCall(null)
        updateIncomingCall(null)
        updateCallState("failed")
        setError("The call could not connect. Please try again.")
        reloadHistory()
      }, SETUP_TIMEOUT_MS)
    },
    [
      caseId,
      cleanupPeerConnection,
      clearSetupTimeout,
      reloadHistory,
      updateActiveCall,
      updateCallState,
      updateIncomingCall,
    ],
  )

  const initPeerConnection = useCallback(
    (callId: number): RTCPeerConnection => {
      if (pcRef.current) {
        pcRef.current.close()
      }

      const pc = new RTCPeerConnection(getIceServers())
      pcRef.current = pc

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          sendSignal({
            type: "ice_candidate",
            call_id: callId,
            candidate: event.candidate.toJSON(),
          })
        }
      }

      pc.ontrack = (event) => {
        const stream = event.streams[0]
        if (!stream) return
        remoteStreamRef.current = stream
        if (remoteAudioRef.current) {
          remoteAudioRef.current.srcObject = stream
          void remoteAudioRef.current.play().catch(() => {
            /* Handled gracefully if the browser requires a user gesture. */
          })
        }
      }

      pc.onconnectionstatechange = () => {
        if (pcRef.current !== pc) return
        const update = connectionStateUpdate(pc.connectionState)
        if (update.state) updateCallState(update.state)
        if (update.error) setError(update.error)
        else if (pc.connectionState === "connected") {
          clearSetupTimeout()
          setError(null)
        }

        if (pc.connectionState === "failed") {
          void endCall(caseId, callId, "connection_failed").catch(() => {})
          cleanupPeerConnection()
          updateActiveCall(null)
          updateIncomingCall(null)
          updateCallState("failed")
          reloadHistory()
        } else if (pc.connectionState === "closed") {
          cleanupPeerConnection()
          updateActiveCall(null)
          updateIncomingCall(null)
          updateCallState("ended")
          reloadHistory()
        }
      }

      return pc
    },
    [
      caseId,
      cleanupPeerConnection,
      clearSetupTimeout,
      reloadHistory,
      sendSignal,
      updateActiveCall,
      updateCallState,
      updateIncomingCall,
    ],
  )

  const syncActiveCall = useCallback(
    async (isDisposed: () => boolean) => {
      try {
        const response = await getActiveCall(caseId)
        if (isDisposed()) return
        const call = response.active_call
        const me = currentUserRef.current?.id ?? null

        if (!call) {
          if (isCallInProgress(callStateRef.current)) {
            cleanupPeerConnection()
            updateActiveCall(null)
            updateIncomingCall(null)
            updateCallState("ended")
          }
          return
        }

        if (call.status === "RINGING") {
          if (call.receiver_id === me) {
            const decision = incomingCallDecision({
              call,
              userId: me,
              callState: callStateRef.current,
              activeCallId: activeCallRef.current?.id ?? null,
              incomingCallId: incomingCallRef.current?.id ?? null,
            })
            if (decision === "reject_busy") {
              await rejectCall(caseId, call.id, "busy").catch(() => {})
              return
            }
            setError(null)
            updateActiveCall(call)
            updateIncomingCall(call)
            updateCallState("ringing")
            scheduleRingTimeout(call.id)
            return
          }

          if (call.caller_id === me) {
            updateActiveCall(call)
            const pc = pcRef.current
            if (pc && pc.connectionState !== "closed" && pc.connectionState !== "failed") {
              if (callStateRef.current === "idle" || callStateRef.current === "ended") {
                updateCallState("calling")
              }
              // Signaling frames are not persisted. After a socket reconnect,
              // resend the local offer so the receiver can still answer.
              if (pc.localDescription?.type === "offer" && !pc.remoteDescription) {
                sendSignal({ type: "offer", call_id: call.id, sdp: pc.localDescription })
              }
              return
            }

            // A page reload/reconnect cannot restore the local offer and media
            // pipeline, so end the orphaned ringing call instead of leaving the
            // UI stuck on a call it cannot complete.
            setError("A previous ringing call could not be restored.")
            await endCall(caseId, call.id, "connection_lost").catch(() => {})
            cleanupPeerConnection()
            updateActiveCall(null)
            updateCallState("ended")
            reloadHistory()
          }
          return
        }

        if (call.status === "ACCEPTED") {
          clearRingTimeout()
          updateActiveCall(call)
          const pc = pcRef.current
          if (pc && pc.connectionState !== "closed" && pc.connectionState !== "failed") {
            if (pc.connectionState === "connected") {
              clearSetupTimeout()
              updateCallState("connected")
            } else {
              updateCallState("connecting")
              scheduleSetupTimeout(call.id)
            }
            // Replay our last SDP so a peer that reconnected can recover the
            // handshake even though the signaling service does not persist it.
            if (pc.localDescription && !pc.remoteDescription) {
              sendSignal({
                type: pc.localDescription.type === "offer" ? "offer" : "answer",
                call_id: call.id,
                sdp: pc.localDescription,
              })
            }
            return
          }

          setError("The active call could not be restored after reconnecting.")
          await endCall(caseId, call.id, "connection_lost").catch(() => {})
          cleanupPeerConnection()
          updateActiveCall(null)
          updateIncomingCall(null)
          updateCallState("ended")
          reloadHistory()
        }
      } catch {
        /* best effort; the socket remains connected for retries */
      }
    },
    [
      caseId,
      cleanupPeerConnection,
      clearRingTimeout,
      clearSetupTimeout,
      reloadHistory,
      scheduleRingTimeout,
      scheduleSetupTimeout,
      sendSignal,
      updateActiveCall,
      updateCallState,
      updateIncomingCall,
    ],
  )

  // Dedicated WebSocket for WebRTC signaling.
  useEffect(() => {
    if (!enabled || !caseId || !currentUser?.id) {
      setWsStatus("offline")
      return
    }

    let disposed = false
    let attempts = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let pingTimer: ReturnType<typeof setInterval> | null = null
    let socket: WebSocket | null = null

    const clearReconnect = () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    const stopPing = () => {
      if (pingTimer) {
        clearInterval(pingTimer)
        pingTimer = null
      }
    }

    const scheduleReconnect = () => {
      if (disposed) return
      const delay = backoffDelay(attempts, {
        baseMs: BASE_BACKOFF_MS,
        maxMs: MAX_BACKOFF_MS,
        jitter: 0.25,
      })
      attempts += 1
      clearReconnect()
      reconnectTimer = setTimeout(connect, delay)
    }

    async function handleFrame(payload: {
      type?: string
      call?: CallRead
      call_id?: number
      sdp?: RTCSessionDescriptionInit
      candidate?: RTCIceCandidateInit
      reason?: string
      user_id?: number
      code?: string
    }) {
      if (disposed) return
      const kind = payload.type

      if (kind === "ready") {
        attempts = 0
        setWsStatus("online")
        stopPing()
        pingTimer = setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }))
          }
        }, PING_INTERVAL_MS)
        await syncActiveCall(() => disposed)
        return
      }

      if (kind === "call_incoming") {
        const call = payload.call
        if (!call) return
        const me = currentUserRef.current?.id ?? null
        if (call.caller_id === me) {
          updateActiveCall(call)
          reloadHistory()
          return
        }

        const decision = incomingCallDecision({
          call,
          userId: me,
          callState: callStateRef.current,
          activeCallId: activeCallRef.current?.id ?? null,
          incomingCallId: incomingCallRef.current?.id ?? null,
        })
        if (decision === "reject_busy") {
          await rejectCall(caseId, call.id, "busy").catch(() => {})
          return
        }
        if (decision === "notify") {
          setError(null)
          updateActiveCall(call)
          updateIncomingCall(call)
          updateCallState("ringing")
          scheduleRingTimeout(call.id)
          reloadHistory()
        }
        return
      }

      if (kind === "offer") {
        if (!payload.sdp || !payload.call_id) return
        const currentId = activeCallRef.current?.id ?? incomingCallRef.current?.id ?? null
        if (currentId !== null && payload.call_id !== currentId) return
        pendingOfferRef.current = payload.sdp
        const pc = pcRef.current
        if (!pc || pc.signalingState === "closed") return
        await applyPendingOffer(pc, payload.call_id)
        return
      }

      if (kind === "answer") {
        if (!payload.sdp) return
        const currentId = activeCallRef.current?.id ?? incomingCallRef.current?.id ?? null
        if (payload.call_id && currentId !== null && payload.call_id !== currentId) return
        const pc = pcRef.current
        if (!pc || pc.signalingState === "closed" || pc.remoteDescription) return
        try {
          await pc.setRemoteDescription(new RTCSessionDescription(payload.sdp))
          await drainPendingIceCandidates(pc)
          clearRingTimeout()
          updateCallState("connecting")
        } catch {
          setError("The call could not be established.")
        }
        return
      }

      if (kind === "ice_candidate") {
        if (!payload.candidate) return
        const currentId = activeCallRef.current?.id ?? incomingCallRef.current?.id ?? null
        if (payload.call_id && currentId !== null && payload.call_id !== currentId) return
        const pc = pcRef.current
        if (
          pc &&
          pc.signalingState !== "closed" &&
          !shouldQueueIceCandidate(pc.remoteDescription)
        ) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(payload.candidate))
          } catch {
            /* stale candidate */
          }
        } else {
          pendingIceCandidatesRef.current.push(payload.candidate)
        }
        return
      }

      if (kind === "call_accepted") {
        if (!payload.call) return
        const currentId = activeCallRef.current?.id ?? incomingCallRef.current?.id ?? null
        if (currentId !== null && payload.call.id !== currentId) return
        updateActiveCall(payload.call)
        updateIncomingCall(null)
        clearRingTimeout()
        const pc = pcRef.current
        if (pc?.connectionState === "connected") {
          clearSetupTimeout()
          updateCallState("connected")
        } else if (isCallInProgress(callStateRef.current)) {
          updateCallState("connecting")
          scheduleSetupTimeout(payload.call.id)
        }
        return
      }

      if (kind === "call_rejected") {
        const rejectedId = payload.call?.id
        const currentId = activeCallRef.current?.id ?? incomingCallRef.current?.id ?? null
        if (rejectedId != null && currentId != null && rejectedId !== currentId) {
          reloadHistory()
          return
        }
        const locallyHandled = localTerminalCallRef.current === rejectedId
        localTerminalCallRef.current = null
        cleanupPeerConnection()
        updateActiveCall(null)
        updateIncomingCall(null)
        updateCallState("ended")
        if (!locallyHandled) {
          setError(payload.reason ? `Call declined: ${payload.reason}` : "Call was declined.")
        }
        reloadHistory()
        return
      }

      if (kind === "call_ended") {
        const endedId = payload.call?.id
        const currentId = activeCallRef.current?.id ?? incomingCallRef.current?.id ?? null
        if (endedId != null && currentId != null && endedId !== currentId) {
          reloadHistory()
          return
        }
        localTerminalCallRef.current = null
        cleanupPeerConnection()
        updateActiveCall(null)
        updateIncomingCall(null)
        updateCallState("ended")
        reloadHistory()
        return
      }

      if (kind === "peer_disconnected") {
        if (!activeCallRef.current && !incomingCallRef.current && !isCallInProgress(callStateRef.current)) {
          return
        }
        cleanupPeerConnection()
        updateActiveCall(null)
        updateIncomingCall(null)
        updateCallState("ended")
        setError("The other party disconnected.")
        reloadHistory()
        return
      }

      if (kind === "error") {
        if (payload.code === "not_authorized") {
          setError("You are not authorized to participate in calls for this case.")
          socket?.close()
        } else if (payload.code === "forbidden_call") {
          setError("You are not a participant in this call.")
        }
      }
    }

    function connect() {
      if (disposed) return
      if (!getAuthToken()) {
        setWsStatus("offline")
        return
      }
      setWsStatus("connecting")

      let next: WebSocket
      try {
        next = new WebSocket(websocketUrl(`/cases/${caseId}/calls/ws`))
      } catch {
        setWsStatus("offline")
        scheduleReconnect()
        return
      }
      socket = next
      socketRef.current = next

      next.onopen = () => {
        // Token travels in the first frame, never the URL.
        next.send(JSON.stringify({ type: "auth", token: getAuthToken() }))
      }

      next.onmessage = (event) => {
        let payload: {
          type?: string
          call?: CallRead
          call_id?: number
          sdp?: RTCSessionDescriptionInit
          candidate?: RTCIceCandidateInit
          reason?: string
          user_id?: number
          code?: string
        }
        try {
          payload = JSON.parse(event.data as string)
        } catch {
          return
        }
        if (!payload || typeof payload !== "object") return
        void handleFrame(payload)
      }

      next.onclose = (event) => {
        if (socket === next) socket = null
        stopPing()
        if (disposed) return
        setWsStatus("offline")
        if (event.code === 4400 || event.code === 4401 || event.code === 4403) {
          setError(
            event.code === 4403
              ? "You are not authorized to participate in calls for this case."
              : "Your session is no longer valid. Please sign in again.",
          )
          return
        }
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
      stopPing()

      if (socket) {
        // Best-effort hangup when navigating away or unmounting mid-call.
        if (
          isWebSocketOpen(socket) &&
          activeCallRef.current &&
          isCallInProgress(callStateRef.current)
        ) {
          try {
            socket.send(
              JSON.stringify({
                type: "call_hangup",
                call_id: activeCallRef.current.id,
              }),
            )
          } catch {
            /* closing */
          }
        }
        socket.onopen = null
        socket.onmessage = null
        socket.onclose = null
        socket.onerror = null
        try {
          socket.close()
        } catch {
          /* already closed */
        }
        socket = null
        socketRef.current = null
      }
      cleanupPeerConnection()
    }
  }, [
    caseId,
    cleanupPeerConnection,
    clearRingTimeout,
    clearSetupTimeout,
    currentUser?.id,
    drainPendingIceCandidates,
    enabled,
    applyPendingOffer,
    reloadHistory,
    scheduleRingTimeout,
    scheduleSetupTimeout,
    syncActiveCall,
    updateActiveCall,
    updateCallState,
    updateIncomingCall,
  ])

  const startCall = useCallback(async (): Promise<boolean> => {
    if (!enabled) {
      setError("Voice calling is not available for this case.")
      return false
    }
    if (!canStartCall(callStateRef.current)) return false
    if (!currentUserRef.current) {
      setError("Sign in before starting a call.")
      return false
    }
    if (!isWebSocketOpen(socketRef.current)) {
      setError("Voice calling is offline. Reconnecting to the signaling service…")
      return false
    }

    setError(null)
    let stream: MediaStream
    try {
      stream = await getMicrophoneStream()
    } catch (caught) {
      updateCallState("idle")
      setError(describeError(caught, "Microphone access failed."))
      return false
    }

    let created: CallRead | null = null
    updateCallState("calling")
    try {
      const call = await initiateCall(caseId)
      created = call
      updateActiveCall(call)

      const pc = initPeerConnection(call.id)
      stream.getAudioTracks().forEach((track) => pc.addTrack(track, stream))

      const offer = await pc.createOffer({ offerToReceiveAudio: true })
      await pc.setLocalDescription(offer)
      if (!sendSignal({ type: "offer", call_id: call.id, sdp: offer })) {
        throw new Error("The signaling connection closed before the call could start.")
      }
      scheduleRingTimeout(call.id)
      return true
    } catch (caught) {
      if (created) {
        await endCall(caseId, created.id, "setup_failed").catch(() => {})
      }
      cleanupPeerConnection()
      updateActiveCall(null)
      updateIncomingCall(null)
      updateCallState("failed")
      setError(describeError(caught, "Failed to initiate the voice call."))
      return false
    }
  }, [
    caseId,
    cleanupPeerConnection,
    enabled,
    getMicrophoneStream,
    initPeerConnection,
    scheduleRingTimeout,
    sendSignal,
    updateActiveCall,
    updateCallState,
    updateIncomingCall,
  ])

  const acceptIncomingCall = useCallback(async (): Promise<boolean> => {
    const incoming = incomingCallRef.current
    const me = currentUserRef.current?.id ?? null
    if (
      !enabled ||
      !incoming ||
      !canAcceptIncomingCall(incoming, me, callStateRef.current)
    ) {
      return false
    }
    if (!isWebSocketOpen(socketRef.current)) {
      setError("Voice calling is offline. Reconnecting to the signaling service…")
      return false
    }

    setError(null)
    let stream: MediaStream
    try {
      stream = await getMicrophoneStream()
    } catch (caught) {
      updateCallState("ringing")
      setError(describeError(caught, "Microphone access failed."))
      return false
    }

    let accepted: CallRead | null = null
    updateCallState("connecting")
    try {
      accepted = await acceptCall(caseId, incoming.id)
      updateActiveCall(accepted)
      updateIncomingCall(null)
      clearRingTimeout()

      const pc = initPeerConnection(accepted.id)
      stream.getAudioTracks().forEach((track) => pc.addTrack(track, stream))
      scheduleSetupTimeout(accepted.id)
      await applyPendingOffer(pc, accepted.id)
      return true
    } catch (caught) {
      if (accepted) {
        await endCall(caseId, accepted.id, "setup_failed").catch(() => {})
      }
      cleanupPeerConnection()
      updateActiveCall(null)
      updateIncomingCall(null)
      updateCallState("failed")
      setError(describeError(caught, "Could not accept the call."))
      return false
    }
  }, [
    applyPendingOffer,
    caseId,
    cleanupPeerConnection,
    clearRingTimeout,
    enabled,
    getMicrophoneStream,
    initPeerConnection,
    scheduleSetupTimeout,
    updateActiveCall,
    updateCallState,
    updateIncomingCall,
  ])

  const rejectIncomingCall = useCallback(
    async (reason?: string): Promise<boolean> => {
      const incoming = incomingCallRef.current
      const me = currentUserRef.current?.id ?? null
      if (!incoming || !canRejectIncomingCall(incoming, me)) return false

      localTerminalCallRef.current = incoming.id
      try {
        await rejectCall(caseId, incoming.id, reason)
        cleanupPeerConnection()
        updateActiveCall(null)
        updateIncomingCall(null)
        updateCallState("idle")
        reloadHistory()
        return true
      } catch (caught) {
        setError(describeError(caught, "Could not reject the call."))
        return false
      }
    },
    [
      caseId,
      cleanupPeerConnection,
      reloadHistory,
      updateActiveCall,
      updateCallState,
      updateIncomingCall,
    ],
  )

  const endActiveCall = useCallback(
    async (reason?: string): Promise<boolean> => {
      const target = activeCallRef.current ?? incomingCallRef.current
      if (!target) {
        cleanupPeerConnection()
        updateCallState("idle")
        return true
      }

      localTerminalCallRef.current = target.id
      try {
        await endCall(caseId, target.id, reason)
        cleanupPeerConnection()
        updateActiveCall(null)
        updateIncomingCall(null)
        updateCallState("ended")
        reloadHistory()
        return true
      } catch (caught) {
        cleanupPeerConnection()
        updateActiveCall(null)
        updateIncomingCall(null)
        updateCallState("idle")
        setError(describeError(caught, "Could not end the call."))
        return false
      }
    },
    [
      caseId,
      cleanupPeerConnection,
      reloadHistory,
      updateActiveCall,
      updateCallState,
      updateIncomingCall,
    ],
  )

  const toggleMute = useCallback(() => {
    const tracks = localStreamRef.current?.getAudioTracks() ?? []
    setIsMuted((previous) => toggleTrackMute(tracks, previous))
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return {
    activeCall,
    incomingCall,
    callState,
    isMuted,
    duration,
    remoteAudioRef,
    error,
    history,
    loadingHistory,
    wsStatus,
    startCall,
    acceptIncomingCall,
    rejectIncomingCall,
    endActiveCall,
    toggleMute,
    reloadHistory,
    clearError,
  }
}
