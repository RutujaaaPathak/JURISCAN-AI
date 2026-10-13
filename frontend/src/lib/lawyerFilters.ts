/**
 * Pure, framework-free helpers for the client-facing lawyer directory. Kept
 * dependency-free so they can be unit tested with node:test.
 */

export const CONSULTATION_MODE_OPTIONS = [
  { value: "all", label: "Any format" },
  { value: "video", label: "Video call" },
  { value: "phone", label: "Phone" },
  { value: "in-person", label: "In person" },
  { value: "chat", label: "Chat" },
]

export const EXPERIENCE_OPTIONS = [
  { value: "any", label: "Any experience" },
  { value: "3", label: "3+ years" },
  { value: "5", label: "5+ years" },
  { value: "10", label: "10+ years" },
  { value: "15", label: "15+ years" },
]

export interface LawyerSearchQuery {
  q?: string
  category?: string
  location?: string
  min_experience?: number
  consultation_mode?: string
  verified_only?: boolean
  limit?: number
  offset?: number
}

export function buildLawyerSearch(query: LawyerSearchQuery): string {
  const search = new URLSearchParams()
  const q = query.q?.trim()
  if (q) search.set("q", q)
  if (query.category && query.category !== "all") search.set("category", query.category)
  const location = query.location?.trim()
  if (location) search.set("location", location)
  if (query.consultation_mode && query.consultation_mode !== "all") {
    search.set("consultation_mode", query.consultation_mode)
  }
  if (query.min_experience !== undefined && query.min_experience > 0) {
    search.set("min_experience", String(query.min_experience))
  }
  if (query.verified_only) search.set("verified_only", "true")
  if (query.limit !== undefined) search.set("limit", String(query.limit))
  if (query.offset !== undefined) search.set("offset", String(query.offset))
  return search.toString()
}

export function verificationLabel(status: string): string {
  switch (status) {
    case "VERIFIED":
      return "Verified"
    case "PENDING":
      return "Pending review"
    case "REJECTED":
      return "Rejected"
    default:
      return "Unverified"
  }
}

export function consultationModeLabel(value: string): string {
  const match = CONSULTATION_MODE_OPTIONS.find((option) => option.value === value.toLowerCase())
  if (match) return match.label
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** Two-letter monogram for an avatar; never fabricates a name for a blank one. */
export function initials(name: string | null | undefined): string {
  const trimmed = (name ?? "").trim()
  if (!trimmed) return "?"
  const parts = trimmed.split(/\s+/).slice(0, 2)
  return parts.map((part) => part.charAt(0).toUpperCase()).join("")
}

export function experienceLabel(years: number | null): string {
  if (years === null) return "Experience not stated"
  if (years <= 0) return "Newly practising"
  if (years === 1) return "1 year experience"
  return `${years} years experience`
}
