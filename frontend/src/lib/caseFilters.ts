import type { CaseSummary } from "@/lib/types"

/**
 * Pure, framework-free helpers for the lawyer case views. Kept dependency-free
 * (type-only imports are erased) so they can be unit tested with node:test.
 */

export const CASE_CATEGORY_VALUES = [
  "property",
  "family",
  "employment",
  "business",
  "consumer",
  "cybercrime",
  "criminal",
  "immigration",
  "intellectual_property",
  "tax",
  "other",
] as const

export const CASE_CATEGORY_OPTIONS = [
  { value: "all", label: "All categories" },
  ...CASE_CATEGORY_VALUES.map((value) => ({ value, label: caseCategoryLabel(value) })),
]

export const CASE_URGENCY_VALUES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const

export const CASE_URGENCY_OPTIONS = [
  { value: "ALL", label: "Any urgency" },
  ...CASE_URGENCY_VALUES.map((value) => ({ value, label: urgencyLabel(value) })),
]

export const CASE_SORT_OPTIONS = [
  { value: "recent", label: "Most recent" },
  { value: "urgency", label: "Most urgent" },
  { value: "oldest", label: "Oldest first" },
]

export interface CaseListQuery {
  q?: string
  category?: string
  urgency?: string
  sort?: string
  limit?: number
  offset?: number
}

export function buildCaseListSearch(query: CaseListQuery): string {
  const search = new URLSearchParams()
  const entries: [string, string | number | undefined][] = [
    ["q", query.q?.trim() || undefined],
    ["category", query.category && query.category !== "all" ? query.category : undefined],
    ["urgency", query.urgency && query.urgency !== "ALL" ? query.urgency : undefined],
    ["sort", query.sort],
    ["limit", query.limit],
    ["offset", query.offset],
  ]
  for (const [key, value] of entries) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value))
    }
  }
  return search.toString()
}

export function caseCategoryLabel(value: string): string {
  if (value === "all") return "All categories"
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

export function urgencyLabel(value: string): string {
  const upper = value.toUpperCase()
  if (upper === "ALL") return "Any urgency"
  return upper.charAt(0) + upper.slice(1).toLowerCase()
}

export function urgencyRank(value: string): number {
  const index = CASE_URGENCY_VALUES.indexOf(value.toUpperCase() as (typeof CASE_URGENCY_VALUES)[number])
  return index === -1 ? CASE_URGENCY_VALUES.length : index
}

export type UrgencyTone = "destructive" | "warning" | "default"

export function urgencyTone(value: string): UrgencyTone {
  switch (value.toUpperCase()) {
    case "CRITICAL":
      return "destructive"
    case "HIGH":
      return "warning"
    default:
      return "default"
  }
}

export function caseStatusLabel(status: string): string {
  switch (status) {
    case "OPEN":
      return "Open"
    case "ASSIGNED":
      return "Active"
    case "COMPLETED":
      return "Completed"
    case "CLOSED":
      return "Closed"
    default:
      return status
  }
}

export function decisionLabel(decision: string | null): string {
  switch (decision) {
    case "ACCEPT":
      return "Accepted"
    case "REJECT":
      return "Declined"
    case "REQUEST_INFO":
      return "Information requested"
    default:
      return "No action yet"
  }
}

/** Counts cases by category for the overview chart, highest first. */
export function countByCategory(cases: CaseSummary[]): { label: string; value: number }[] {
  const counts = new Map<string, number>()
  for (const item of cases) {
    counts.set(item.category, (counts.get(item.category) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([category, value]) => ({ label: caseCategoryLabel(category), value }))
    .sort((a, b) => b.value - a.value)
}
