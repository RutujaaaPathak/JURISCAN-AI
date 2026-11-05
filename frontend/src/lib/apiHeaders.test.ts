import assert from "node:assert/strict"
import { test } from "node:test"

import { bearerHeaders, reportRequestHeaders } from "./apiHeaders.ts"

test("bearerHeaders returns an Authorization header when a token is present", () => {
  assert.deepEqual(bearerHeaders("abc123"), { Authorization: "Bearer abc123" })
})

test("bearerHeaders returns no headers without a token", () => {
  assert.deepEqual(bearerHeaders(null), {})
})

test("reportRequestHeaders requests a PDF and attaches the session token", () => {
  assert.deepEqual(reportRequestHeaders("abc123"), {
    Accept: "application/pdf",
    Authorization: "Bearer abc123",
  })
})

test("reportRequestHeaders still requests a PDF with no token (dev fallback)", () => {
  assert.deepEqual(reportRequestHeaders(null), { Accept: "application/pdf" })
})
