import assert from "node:assert/strict"
import { test } from "node:test"

import type { ClauseRead, DocumentPage } from "@/lib/types"
import { buildTextBlocks, buildTextPages, findMatches } from "./extractedText.ts"

function clause(overrides: Partial<ClauseRead> & Pick<ClauseRead, "id">): ClauseRead {
  return {
    document_id: 1,
    clause_number: overrides.id,
    heading: null,
    text: "",
    start_offset: 0,
    end_offset: 0,
    page_number: null,
    clause_type: null,
    risk_level: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}

test("findMatches is literal and case-insensitive", () => {
  const matches = findMatches("Indemnity and indemnity.", "indemnity")
  assert.equal(matches.length, 2)
  assert.deepEqual(matches[0], { start: 0, end: 9 })
  assert.deepEqual(matches[1], { start: 14, end: 23 })
})

test("findMatches does not treat the query as a regular expression", () => {
  assert.deepEqual(findMatches("a.b a_b", "a."), [{ start: 0, end: 2 }])
  assert.deepEqual(findMatches("value (100)", "(100)"), [{ start: 6, end: 11 }])
})

test("findMatches returns nothing for a blank query", () => {
  assert.deepEqual(findMatches("some text", "   "), [])
  assert.deepEqual(findMatches("", "term"), [])
})

test("buildTextBlocks covers the whole text and links clauses", () => {
  const text = "Preamble.\n\n1. Indemnity\nSupplier indemnifies.\n\n2. Payment\nDue in 90 days."
  const clauses = [
    clause({ id: 1, start_offset: 11, end_offset: 42, page_number: 1 }),
    clause({ id: 2, start_offset: 44, end_offset: 66, page_number: 1 }),
  ]
  const blocks = buildTextBlocks(text, clauses)

  assert.equal(blocks[0].key, "text-lead")
  assert.equal(blocks[0].text, "Preamble.\n\n")
  assert.equal(blocks[1].clauseId, 1)
  assert.equal(blocks[2].clauseId, 2)
  // Contiguous: no gaps, no overlaps, full coverage.
  assert.equal(blocks[0].start, 0)
  assert.equal(blocks[blocks.length - 1].end, text.length)
  for (let index = 1; index < blocks.length; index += 1) {
    assert.equal(blocks[index].start, blocks[index - 1].end)
  }
})

test("buildTextPages never invents page numbers for unpaginated text", () => {
  const text = "1. Clause\nBody text here.\n\n2. Clause\nMore text."
  const pages = buildTextPages(text, [], [])
  assert.equal(pages.length, 1)
  assert.equal(pages[0].pageNumber, null)
  assert.equal(pages[0].blocks[0].pageNumber, null)
})

test("buildTextPages maps blocks to their source pages", () => {
  const text = "Alpha page one.\n\nBeta page two."
  const split = text.indexOf("Beta")
  const pages: DocumentPage[] = [
    { page_number: 1, start_offset: 0, end_offset: split },
    { page_number: 2, start_offset: split, end_offset: text.length },
  ]
  const clauses = [
    clause({ id: 1, start_offset: 0, end_offset: split - 2, page_number: 1 }),
    clause({ id: 2, start_offset: split, end_offset: text.length, page_number: 2 }),
  ]
  const sections = buildTextPages(text, pages, clauses)

  assert.deepEqual(
    sections.map((section) => section.pageNumber),
    [1, 2],
  )
  assert.equal(sections[0].blocks[0].clauseId, 1)
  assert.equal(sections[1].blocks[0].clauseId, 2)
})
