import assert from "node:assert/strict"
import { test } from "node:test"

import type { CallRead, CallState } from "@/lib/types"
import {
  canAcceptIncomingCall,
  canEndCall,
  canRejectIncomingCall,
  canStartCall,
  connectionStateUpdate,
  incomingCallDecision,
  isCallInProgress,
  otherPartyName,
  shouldQueueIceCandidate,
  toggleTrackMute,
} from "./callState.ts"

function call(overrides: Partial<CallRead> = {}): CallRead {
  return {
    id: 1,
    case_id: 10,
    caller_id: 1,
    receiver_id: 2,
    caller_name: "Client",
    receiver_name: "Lawyer",
    status: "RINGING",
    answered_at: null,
    ended_at: null,
    duration: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}

test("incoming call notifies only the intended receiver", () => {
  const incoming = call()
  assert.equal(
    incomingCallDecision({
      call: incoming,
      userId: 2,
      callState: "idle",
      activeCallId: null,
      incomingCallId: null,
    }),
    "notify",
  )
  assert.equal(
    incomingCallDecision({
      call: incoming,
      userId: 1,
      callState: "idle",
      activeCallId: null,
      incomingCallId: null,
    }),
    "ignore",
  )
})

test("incoming call is rejected as busy while another call is in progress", () => {
  assert.equal(
    incomingCallDecision({
      call: call({ id: 7 }),
      userId: 2,
      callState: "connected",
      activeCallId: 3,
      incomingCallId: null,
    }),
    "reject_busy",
  )
  assert.equal(
    incomingCallDecision({
      call: call({ id: 7 }),
      userId: 2,
      callState: "idle",
      activeCallId: 3,
      incomingCallId: null,
    }),
    "reject_busy",
  )
})

test("duplicate incoming frames keep the current notification", () => {
  assert.equal(
    incomingCallDecision({
      call: call({ id: 7 }),
      userId: 2,
      callState: "ringing",
      activeCallId: 7,
      incomingCallId: 7,
    }),
    "notify",
  )
})

test("call start is only allowed from idle or terminal states", () => {
  const allowed: CallState[] = ["idle", "ended", "failed"]
  const blocked: CallState[] = [
    "requesting_permission",
    "calling",
    "ringing",
    "connecting",
    "connected",
  ]
  for (const state of allowed) assert.equal(canStartCall(state), true, state)
  for (const state of blocked) assert.equal(canStartCall(state), false, state)
})

test("accept and reject are restricted to the receiver of a ringing call", () => {
  const ringing = call()
  assert.equal(canAcceptIncomingCall(ringing, 2, "ringing"), true)
  assert.equal(canAcceptIncomingCall(ringing, 2, "idle"), true)
  assert.equal(canAcceptIncomingCall(ringing, 1, "ringing"), false)
  assert.equal(canAcceptIncomingCall(ringing, 2, "calling"), false)
  assert.equal(canAcceptIncomingCall(ringing, 2, "connected"), false)
  assert.equal(canRejectIncomingCall(ringing, 2), true)
  assert.equal(canRejectIncomingCall(ringing, 1), false)
})

test("ending is allowed for ringing and accepted calls only", () => {
  assert.equal(canEndCall(call({ status: "RINGING" })), true)
  assert.equal(canEndCall(call({ status: "ACCEPTED" })), true)
  assert.equal(canEndCall(call({ status: "ENDED" })), false)
  assert.equal(canEndCall(null), false)
})

test("mute toggles every local track and reports the new state", () => {
  const tracks = [{ enabled: true }, { enabled: true }]
  const muted = toggleTrackMute(tracks, false)
  assert.equal(muted, true)
  assert.deepEqual(
    tracks.map((track) => track.enabled),
    [false, false],
  )

  const unmuted = toggleTrackMute(tracks, true)
  assert.equal(unmuted, false)
  assert.deepEqual(
    tracks.map((track) => track.enabled),
    [true, true],
  )
})

test("mute with no local tracks leaves the state unchanged", () => {
  assert.equal(toggleTrackMute([], false), false)
  assert.equal(toggleTrackMute([], true), true)
})

test("connection failures map to a failed call state with an error", () => {
  assert.deepEqual(connectionStateUpdate("failed"), {
    state: "failed",
    error: "Voice call connection failed.",
  })
  assert.equal(connectionStateUpdate("connected").state, "connected")
  assert.equal(connectionStateUpdate("disconnected").state, "connecting")
  assert.equal(connectionStateUpdate("connecting").state, "connecting")
})

test("call progress states are recognised consistently", () => {
  assert.equal(isCallInProgress("connected"), true)
  assert.equal(isCallInProgress("ringing"), true)
  assert.equal(isCallInProgress("idle"), false)
  assert.equal(isCallInProgress("ended"), false)
})

test("the other party name is resolved from the current user's perspective", () => {
  const ringing = call()
  assert.equal(otherPartyName(ringing, 1), "Lawyer")
  assert.equal(otherPartyName(ringing, 2), "Client")
  assert.equal(otherPartyName(null, 1), "Participant")
})

test("ICE candidates are buffered until a remote description exists", () => {
  assert.equal(shouldQueueIceCandidate(null), true)
  assert.equal(
    shouldQueueIceCandidate({ type: "offer", sdp: "v=0" } as RTCSessionDescription),
    false,
  )
})
