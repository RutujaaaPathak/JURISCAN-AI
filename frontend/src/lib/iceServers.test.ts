import assert from "node:assert/strict"
import { test } from "node:test"

import { buildIceServers } from "./iceServers.ts"

test("uses a public STUN server by default", () => {
  const config = buildIceServers({})
  assert.deepEqual(config.iceServers, [{ urls: "stun:stun.l.google.com:19302" }])
})

test("reads STUN and TURN configuration from environment values", () => {
  const config = buildIceServers({
    stunServer: "stun:stun.example.test:3478",
    turnServer: "turn:turn.example.test:3478",
    turnUsername: "test-user",
    turnCredential: "test-credential",
  })
  assert.deepEqual(config.iceServers, [
    { urls: "stun:stun.example.test:3478" },
    {
      urls: "turn:turn.example.test:3478",
      username: "test-user",
      credential: "test-credential",
    },
  ])
})

test("does not add a TURN entry when no TURN server is configured", () => {
  const config = buildIceServers({ stunServer: "stun:stun.example.test:3478" })
  assert.equal(config.iceServers?.length, 1)
  assert.deepEqual(config.iceServers?.[0], { urls: "stun:stun.example.test:3478" })
})

test("never invents credentials for a TURN server without them", () => {
  const config = buildIceServers({ turnServer: "turn:turn.example.test:3478" })
  const turn = config.iceServers?.[1]
  assert.deepEqual(turn, { urls: "turn:turn.example.test:3478" })
})
