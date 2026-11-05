import type { CallRead, CallState } from "@/lib/types"

/**
 * Pure voice-call state helpers.
 *
 * Kept free of runtime imports (no DOM, no `import.meta.env`) so the call
 * lifecycle can be unit tested with `node --test` without a browser.
 */

export const RING_TIMEOUT_MS = 60_000

const IN_PROGRESS_STATES: ReadonlySet<CallState> = new Set([
  "requesting_permission",
  "calling",
  "ringing",
  "connecting",
  "connected",
])

export function isCallInProgress(state: CallState): boolean {
  return IN_PROGRESS_STATES.has(state)
}

export function canStartCall(state: CallState): boolean {
  return state === "idle" || state === "ended" || state === "failed"
}

export function canAcceptIncomingCall(
  call: CallRead | null,
  userId: number | null,
  state: CallState,
): boolean {
  const canAcceptState = state === "idle" || state === "ringing"
  return (
    call !== null &&
    call.status === "RINGING" &&
    call.receiver_id === userId &&
    canAcceptState
  )
}

export function canRejectIncomingCall(
  call: CallRead | null,
  userId: number | null,
): boolean {
  return call !== null && call.status === "RINGING" && call.receiver_id === userId
}

export function canEndCall(call: CallRead | null): boolean {
  return call !== null && (call.status === "RINGING" || call.status === "ACCEPTED")
}

export type IncomingCallDecision = "ignore" | "notify" | "reject_busy"

/**
 * Decide what to do with a `call_incoming` signaling frame.
 *
 * - Only the intended receiver is notified.
 * - A duplicate frame for the same call is harmless and keeps the notification.
 * - If this browser is already in another call, the new invitation is rejected
 *   as busy instead of replacing the current call.
 */
export function incomingCallDecision(args: {
  call: CallRead
  userId: number | null
  callState: CallState
  activeCallId: number | null
  incomingCallId: number | null
}): IncomingCallDecision {
  const { call, userId, callState, activeCallId, incomingCallId } = args
  if (call.status !== "RINGING" || call.receiver_id !== userId) {
    return "ignore"
  }
  if (incomingCallId === call.id) {
    return "notify"
  }
  if (isCallInProgress(callState) || activeCallId !== null) {
    return "reject_busy"
  }
  return "notify"
}

export function otherPartyName(call: CallRead | null, userId: number | null): string {
  if (!call) return "Participant"
  if (userId !== null && call.caller_id === userId) {
    return call.receiver_name ?? "Participant"
  }
  if (userId !== null && call.receiver_id === userId) {
    return call.caller_name ?? "Participant"
  }
  return call.receiver_name ?? call.caller_name ?? "Participant"
}

export interface ConnectionUpdate {
  state: CallState | null
  error: string | null
}

/**
 * Map an RTCPeerConnection state to the UI call state. `disconnected` is treated
 * as recoverable; `failed` is terminal and the caller should end the call.
 */
export function connectionStateUpdate(connection: RTCPeerConnectionState): ConnectionUpdate {
  switch (connection) {
    case "connected":
      return { state: "connected", error: null }
    case "connecting":
      return { state: "connecting", error: null }
    case "disconnected":
      return {
        state: "connecting",
        error: "Connection interrupted. Trying to recover…",
      }
    case "failed":
      return { state: "failed", error: "Voice call connection failed." }
    case "closed":
      return { state: "ended", error: null }
    default:
      return { state: null, error: null }
  }
}

/**
 * Toggle mute on a set of local audio tracks. Returns the new muted flag.
 * An empty track list leaves the flag unchanged.
 */
export function toggleTrackMute(
  tracks: ReadonlyArray<{ enabled: boolean }>,
  currentlyMuted: boolean,
): boolean {
  if (tracks.length === 0) return currentlyMuted
  const nextMuted = !currentlyMuted
  for (const track of tracks) {
    track.enabled = !nextMuted
  }
  return nextMuted
}

/** ICE candidates received before the remote description must be buffered. */
export function shouldQueueIceCandidate(
  remoteDescription: RTCSessionDescription | null,
): boolean {
  return remoteDescription === null
}
