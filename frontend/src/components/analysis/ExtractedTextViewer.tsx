import { ChevronLeft, ChevronRight, FileText, Search, X } from "lucide-react"
import {
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react"

import { EmptyState } from "@/components/common/States"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import type { TextBlock } from "@/lib/extractedText"
import { buildTextPages, findMatches } from "@/lib/extractedText"
import type { ClauseRead, DocumentPage } from "@/lib/types"
import { cn } from "@/lib/utils"

export interface ExtractedTextViewerProps {
  text: string | null
  pages: DocumentPage[]
  clauses: ClauseRead[]
  focusClauseId?: number | null
  focusNonce?: number
}

function sectionId(uid: string, pageNumber: number | null): string {
  return pageNumber === null ? `${uid}-page-single` : `${uid}-page-${pageNumber}`
}

export function ExtractedTextViewer({
  text,
  pages,
  clauses,
  focusClauseId = null,
  focusNonce = 0,
}: ExtractedTextViewerProps) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "")
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const [query, setQuery] = useState("")
  const [activeMatch, setActiveMatch] = useState(0)
  const [pageIndex, setPageIndex] = useState(0)

  const source = text ?? ""
  const matches = useMemo(() => findMatches(source, query), [source, query])
  const sections = useMemo(
    () => buildTextPages(source, pages, clauses),
    [source, pages, clauses],
  )
  const pageNumbers = useMemo(
    () =>
      sections
        .map((section) => section.pageNumber)
        .filter((value): value is number => value !== null),
    [sections],
  )

  useEffect(() => {
    setActiveMatch(0)
  }, [query])

  useEffect(() => {
    setPageIndex(0)
  }, [pageNumbers.length])

  useEffect(() => {
    if (matches.length === 0) return
    document
      .getElementById(`${uid}-match-${activeMatch}`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" })
  }, [activeMatch, matches, uid])

  useEffect(() => {
    if (focusClauseId === null) return
    document
      .getElementById(`${uid}-clause-${focusClauseId}`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" })
  }, [focusClauseId, focusNonce, uid, sections])

  const scrollToPage = useCallback((index: number) => {
    const target = pageNumbers[index]
    if (target === undefined) return
    document
      .getElementById(sectionId(uid, target))
      ?.scrollIntoView({ block: "start", behavior: "smooth" })
  }, [pageNumbers, uid])

  const goToPage = useCallback(
    (index: number) => {
      const clamped = Math.min(Math.max(index, 0), pageNumbers.length - 1)
      setPageIndex(clamped)
      scrollToPage(clamped)
    },
    [pageNumbers.length, scrollToPage],
  )

  const cycleMatch = useCallback(
    (delta: number) => {
      if (matches.length === 0) return
      setActiveMatch((current) => (current + delta + matches.length) % matches.length)
    },
    [matches.length],
  )

  const renderBlockText = (block: TextBlock): ReactNode[] => {
    const nodes: ReactNode[] = []
    let cursor = 0
    matches.forEach((match, index) => {
      if (match.start < block.start || match.start >= block.end) return
      const localStart = match.start - block.start
      if (localStart < cursor) return
      const localEnd = Math.min(match.end - block.start, block.text.length)
      if (localStart > cursor) nodes.push(block.text.slice(cursor, localStart))
      nodes.push(
        <mark
          key={`match-${index}`}
          id={`${uid}-match-${index}`}
          className={cn(
            "rounded-sm bg-amber-200/70 text-inherit dark:bg-amber-400/30",
            index === activeMatch && "bg-amber-400 text-amber-950 dark:bg-amber-300",
          )}
        >
          {block.text.slice(localStart, localEnd)}
        </mark>,
      )
      cursor = localEnd
    })
    if (cursor < block.text.length) nodes.push(block.text.slice(cursor))
    return nodes
  }

  if (!source.trim()) {
    return (
      <EmptyState
        icon={FileText}
        title="No extracted text"
        description="This document does not contain any readable text to display."
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="relative w-full sm:w-64">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") cycleMatch(event.shiftKey ? -1 : 1)
              }}
              placeholder="Search extracted text…"
              aria-label="Search extracted text"
              className="pl-9 pr-8"
            />
            {query ? (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            ) : null}
          </div>
          <div className="flex items-center gap-1">
            <span className="min-w-14 text-xs text-muted-foreground" aria-live="polite">
              {query.trim()
                ? matches.length > 0
                  ? `${activeMatch + 1} / ${matches.length}`
                  : "0 matches"
                : ""}
            </span>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Previous match"
              disabled={matches.length === 0}
              onClick={() => cycleMatch(-1)}
            >
              <ChevronLeft aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Next match"
              disabled={matches.length === 0}
              onClick={() => cycleMatch(1)}
            >
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </div>

        {pageNumbers.length > 0 ? (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Previous page"
              disabled={pageIndex === 0}
              onClick={() => goToPage(pageIndex - 1)}
            >
              <ChevronLeft aria-hidden="true" />
            </Button>
            <Select
              value={String(pageNumbers[pageIndex] ?? pageNumbers[0])}
              onChange={(event) => goToPage(pageNumbers.indexOf(Number(event.target.value)))}
              aria-label="Jump to page"
              className="w-32"
            >
              {pageNumbers.map((number) => (
                <option key={number} value={number}>
                  Page {number}
                </option>
              ))}
            </Select>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Next page"
              disabled={pageIndex >= pageNumbers.length - 1}
              onClick={() => goToPage(pageIndex + 1)}
            >
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        ) : null}
      </div>

      <div
        ref={scrollRef}
        className="max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-background"
      >
        {sections.map((section) => (
          <section
            key={section.pageNumber ?? "single"}
            id={sectionId(uid, section.pageNumber)}
            className="scroll-mt-4 border-b border-border/60 last:border-b-0"
          >
            {section.pageNumber !== null ? (
              <div className="sticky top-0 z-10 border-b border-border/60 bg-muted/80 px-4 py-1.5 backdrop-blur">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Page {section.pageNumber}
                </span>
              </div>
            ) : null}
            <div className="px-4 py-3">
              {section.blocks.map((block) => {
                const focused = focusClauseId !== null && block.clauseId === focusClauseId
                return (
                  <div
                    key={block.key}
                    id={block.clauseId !== null ? `${uid}-clause-${block.clauseId}` : undefined}
                    className={cn(
                      "scroll-mt-8 whitespace-pre-wrap break-words text-sm leading-relaxed",
                      block.clauseId !== null && "border-l-2 border-transparent pl-3",
                      focused && "border-primary bg-primary/5",
                    )}
                  >
                    {renderBlockText(block)}
                  </div>
                )
              })}
            </div>
          </section>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        Extracted text is rendered as plain text.{" "}
        {pageNumbers.length > 0
          ? `${pageNumbers.length} page(s) available.`
          : "Page numbers are not available for this format."}
      </p>
    </div>
  )
}
