import type { CaseMessage } from "@/lib/types"

/**
 * Framework-agnostic helpers for the real-time message stream. Kept free of any
 * runtime imports so they can be unit tested with `node --test` (see
 * `messages.test.ts`) without a bundler.
 */

function compareMessages(a: CaseMessage, b: CaseMessage): number {
  const left = Date.parse(a.created_at)
  const right = Date.parse(b.created_at)
  if (!Number.isNaN(left) && !Number.isNaN(right) && left !== right) {
    return left - right
  }
  return a.id - b.id
}

export function sortMessages(messages: CaseMessage[]): CaseMessage[] {
  return [...messages].sort(compareMessages)
}

/**
 * Merge a batch of incoming messages into the current list.
 *
 * Identical ids are collapsed so a message that arrives both in the HTTP send
 * response and as a WebSocket broadcast (the sender's echo) is never shown
 * twice. A newer payload for an existing id wins, which is how a read receipt
 * updates an already-rendered message.
 */
export function mergeMessages(
  existing: CaseMessage[],
  incoming: CaseMessage[],
): CaseMessage[] {
  if (incoming.length === 0) return existing
  const byId = new Map<number, CaseMessage>()
  for (const message of existing) byId.set(message.id, message)
  for (const message of incoming) byId.set(message.id, message)
  return sortMessages([...byId.values()])
}

export interface BackoffOptions {
  baseMs?: number
  maxMs?: number
  /** Fraction (0..1) of the delay to randomise, to avoid reconnect stampedes. */
  jitter?: number
}

/** Bounded exponential backoff: `min(maxMs, baseMs * 2 ** attempt)`. */
export function backoffDelay(attempt: number, options: BackoffOptions = {}): number {
  const baseMs = options.baseMs ?? 1000
  const maxMs = options.maxMs ?? 15000
  const jitter = options.jitter ?? 0
  const safeAttempt = Math.max(0, Math.floor(attempt))
  const delay = Math.min(maxMs, baseMs * 2 ** safeAttempt)
  if (jitter <= 0) return delay
  const spread = delay * jitter
  return Math.round(delay - spread + Math.random() * spread * 2)
}
