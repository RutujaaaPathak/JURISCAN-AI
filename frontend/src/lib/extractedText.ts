import type { ClauseRead, DocumentPage } from "@/lib/types"

export interface TextMatch {
  start: number
  end: number
}

export interface TextBlock {
  key: string
  clauseId: number | null
  pageNumber: number | null
  heading: string | null
  text: string
  start: number
  end: number
}

export interface TextPage {
  pageNumber: number | null
  start: number
  end: number
  blocks: TextBlock[]
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

/**
 * Literal (non-regex) case-insensitive search over the extracted text. Returns
 * absolute character ranges so callers can map matches back to page/clause
 * boundaries. The query is never interpreted as a regular expression, and the
 * number of matches is capped to keep highlighting bounded.
 */
export function findMatches(text: string, query: string, limit = 500): TextMatch[] {
  const term = query.trim().toLowerCase()
  if (!term || !text) return []
  const haystack = text.toLowerCase()
  const matches: TextMatch[] = []
  let from = 0
  while (matches.length < limit) {
    const index = haystack.indexOf(term, from)
    if (index === -1) break
    matches.push({ start: index, end: index + term.length })
    from = index + term.length
  }
  return matches
}

/**
 * Split the full extracted text into contiguous blocks, using clause offsets so
 * each block can be linked back to its clause and findings. Blocks always cover
 * the whole string: any leading/trailing text is preserved in plain blocks.
 */
export function buildTextBlocks(text: string, clauses: ClauseRead[]): TextBlock[] {
  if (!text) return []

  const ordered = clauses
    .filter(
      (clause) => clause.start_offset !== null && clause.end_offset !== null,
    )
    .slice()
    .sort((a, b) => (a.start_offset as number) - (b.start_offset as number))

  if (ordered.length === 0) {
    return [
      {
        key: "text-all",
        clauseId: null,
        pageNumber: null,
        heading: null,
        text,
        start: 0,
        end: text.length,
      },
    ]
  }

  const blocks: TextBlock[] = []
  const firstStart = clamp(ordered[0].start_offset as number, 0, text.length)
  if (firstStart > 0) {
    blocks.push({
      key: "text-lead",
      clauseId: null,
      pageNumber: ordered[0].page_number,
      heading: null,
      text: text.slice(0, firstStart),
      start: 0,
      end: firstStart,
    })
  }

  ordered.forEach((clause, index) => {
    const start = clamp(clause.start_offset as number, 0, text.length)
    const nextStart =
      index + 1 < ordered.length
        ? clamp(ordered[index + 1].start_offset as number, 0, text.length)
        : text.length
    const end = Math.max(start, nextStart)
    if (end <= start) return
    blocks.push({
      key: `clause-${clause.id}`,
      clauseId: clause.id,
      pageNumber: clause.page_number,
      heading: clause.heading,
      text: text.slice(start, end),
      start,
      end,
    })
  })

  const lastEnd = blocks.length > 0 ? blocks[blocks.length - 1].end : 0
  if (lastEnd < text.length) {
    blocks.push({
      key: "text-tail",
      clauseId: null,
      pageNumber: null,
      heading: null,
      text: text.slice(lastEnd),
      start: lastEnd,
      end: text.length,
    })
  }

  return blocks
}

/**
 * Group text blocks into page sections. When the document has no page metadata
 * (DOCX/TXT) a single section with ``pageNumber === null`` is returned so the
 * viewer never invents page numbers.
 */
export function buildTextPages(
  text: string,
  pages: DocumentPage[],
  clauses: ClauseRead[],
): TextPage[] {
  const blocks = buildTextBlocks(text, clauses)
  if (blocks.length === 0) return []

  const ranges = pages
    .filter((page) => page.end_offset > page.start_offset)
    .slice()
    .sort((a, b) => a.start_offset - b.start_offset)

  if (ranges.length === 0) {
    return [{ pageNumber: null, start: 0, end: text.length, blocks }]
  }

  const sections: TextPage[] = ranges.map((range) => ({
    pageNumber: range.page_number,
    start: range.start_offset,
    end: range.end_offset,
    blocks: blocks.filter(
      (block) => block.start >= range.start_offset && block.start < range.end_offset,
    ),
  }))

  const captured = new Set(
    sections.flatMap((section) => section.blocks.map((block) => block.key)),
  )
  const leftovers = blocks.filter((block) => !captured.has(block.key))
  if (leftovers.length > 0) {
    sections[sections.length - 1].blocks.push(...leftovers)
  }

  return sections
}
