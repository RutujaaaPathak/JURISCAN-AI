import assert from "node:assert/strict"
import { test } from "node:test"

import type { CaseSummary } from "@/lib/types"
import {
  buildCaseListSearch,
  caseCategoryLabel,
  caseStatusLabel,
  countByCategory,
  decisionLabel,
  urgencyLabel,
  urgencyRank,
  urgencyTone,
} from "./caseFilters.ts"

function summary(overrides: Partial<CaseSummary> & Pick<CaseSummary, "id">): CaseSummary {
  return {
    title: "Matter",
    category: "property",
    summary: "Summary text",
    jurisdiction: null,
    urgency: "MEDIUM",
    consultation_method: null,
    budget: null,
    contact_preference: null,
    client_reference: null,
    status: "OPEN",
    posted_by_user_id: 1,
    posted_by_name: "Client",
    assigned_lawyer_id: null,
    assigned_lawyer_name: null,
    document_count: 0,
    decision_count: 0,
    my_decision: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    accepted_at: null,
    completed_at: null,
    ...overrides,
  }
}

test("buildCaseListSearch omits empty and sentinel filter values", () => {
  assert.equal(buildCaseListSearch({}), "")
  assert.equal(
    buildCaseListSearch({ q: "  ", category: "all", urgency: "ALL" }),
    "",
  )
})

test("buildCaseListSearch trims the query and keeps real filters", () => {
  const search = buildCaseListSearch({ q: " land ", category: "family", urgency: "HIGH", sort: "urgency", limit: 10, offset: 20 })
  const parsed = new URLSearchParams(search)
  assert.equal(parsed.get("q"), "land")
  assert.equal(parsed.get("category"), "family")
  assert.equal(parsed.get("urgency"), "HIGH")
  assert.equal(parsed.get("sort"), "urgency")
  assert.equal(parsed.get("limit"), "10")
  assert.equal(parsed.get("offset"), "20")
})

test("category and status labels are human readable", () => {
  assert.equal(caseCategoryLabel("intellectual_property"), "Intellectual Property")
  assert.equal(caseCategoryLabel("property"), "Property")
  assert.equal(caseStatusLabel("ASSIGNED"), "Active")
  assert.equal(caseStatusLabel("COMPLETED"), "Completed")
  assert.equal(decisionLabel("REQUEST_INFO"), "Information requested")
  assert.equal(decisionLabel(null), "No action yet")
})

test("urgency helpers rank and tone cases consistently", () => {
  assert.ok(urgencyRank("CRITICAL") < urgencyRank("HIGH"))
  assert.ok(urgencyRank("HIGH") < urgencyRank("LOW"))
  assert.equal(urgencyRank("unknown"), 4)
  assert.equal(urgencyTone("CRITICAL"), "destructive")
  assert.equal(urgencyTone("HIGH"), "warning")
  assert.equal(urgencyTone("LOW"), "default")
  assert.equal(urgencyLabel("ALL"), "Any urgency")
  assert.equal(urgencyLabel("HIGH"), "High")
})

test("countByCategory aggregates and sorts descending", () => {
  const counts = countByCategory([
    summary({ id: 1, category: "property" }),
    summary({ id: 2, category: "family" }),
    summary({ id: 3, category: "property" }),
    summary({ id: 4, category: "property" }),
    summary({ id: 5, category: "family" }),
  ])
  assert.deepEqual(counts, [
    { label: "Property", value: 3 },
    { label: "Family", value: 2 },
  ])
})
