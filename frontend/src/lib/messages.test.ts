import assert from "node:assert/strict"
import { test } from "node:test"

import type { CaseMessage } from "@/lib/types"
import { backoffDelay, mergeMessages, sortMessages } from "./messages.ts"

function message(overrides: Partial<CaseMessage> & Pick<CaseMessage, "id">): CaseMessage {
  return {
    sender_user_id: 1,
    sender_name: "Sender",
    body: "Body",
    read_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}

test("sortMessages orders by created_at then id", () => {
  const later = message({ id: 9, created_at: "2026-01-01T00:02:00Z" })
  const earlier = message({ id: 2, created_at: "2026-01-01T00:01:00Z" })
  const sameTime = message({ id: 3, created_at: "2026-01-01T00:01:00Z" })
  const sorted = sortMessages([later, earlier, sameTime])
  assert.deepEqual(
    sorted.map((item) => item.id),
    [2, 3, 9],
  )
})

test("mergeMessages drops duplicates sent by both HTTP response and socket", () => {
  const original = message({ id: 1, body: "hi" })
  const fromApi = mergeMessages([], [original])
  const echoed = mergeMessages(fromApi, [original])
  assert.equal(echoed.length, 1)
})

test("mergeMessages keeps every distinct message in chronological order", () => {
  const first = message({ id: 1, created_at: "2026-01-01T00:00:00Z" })
  const second = message({ id: 2, created_at: "2026-01-01T00:01:00Z" })
  const merged = mergeMessages([second], [first])
  assert.deepEqual(
    merged.map((item) => item.id),
    [1, 2],
  )
})

test("mergeMessages lets a newer payload for an id win (read receipts)", () => {
  const original = message({ id: 5, read_at: null })
  const updated = message({ id: 5, read_at: "2026-01-01T00:02:00Z" })
  const merged = mergeMessages([original], [updated])
  assert.equal(merged.length, 1)
  assert.equal(merged[0].read_at, "2026-01-01T00:02:00Z")
})

test("mergeMessages returns the same reference when nothing arrives", () => {
  const existing = [message({ id: 1 })]
  assert.equal(mergeMessages(existing, []), existing)
})

test("backoffDelay grows exponentially and is bounded", () => {
  assert.equal(backoffDelay(0, { baseMs: 1000, maxMs: 15000 }), 1000)
  assert.equal(backoffDelay(1, { baseMs: 1000, maxMs: 15000 }), 2000)
  assert.equal(backoffDelay(2, { baseMs: 1000, maxMs: 15000 }), 4000)
  assert.equal(backoffDelay(10, { baseMs: 1000, maxMs: 15000 }), 15000)
})

test("backoffDelay stays within the jitter window", () => {
  for (let index = 0; index < 50; index += 1) {
    const delay = backoffDelay(2, { baseMs: 1000, maxMs: 15000, jitter: 0.25 })
    assert.ok(delay >= 3000 && delay <= 5000, `unexpected delay ${delay}`)
  }
})
