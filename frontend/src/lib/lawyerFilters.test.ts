import assert from "node:assert/strict"
import { test } from "node:test"

import {
  buildLawyerSearch,
  consultationModeLabel,
  experienceLabel,
  initials,
  verificationLabel,
} from "./lawyerFilters.ts"

test("buildLawyerSearch omits empty and sentinel filters", () => {
  assert.equal(buildLawyerSearch({}), "")
  assert.equal(
    buildLawyerSearch({ q: "  ", category: "all", consultation_mode: "all", min_experience: 0 }),
    "",
  )
})

test("buildLawyerSearch keeps real filters and trims input", () => {
  const search = buildLawyerSearch({
    q: "  property  ",
    category: "property",
    location: " Pune ",
    consultation_mode: "video",
    min_experience: 5,
    verified_only: true,
    limit: 20,
    offset: 40,
  })
  const params = new URLSearchParams(search)
  assert.equal(params.get("q"), "property")
  assert.equal(params.get("category"), "property")
  assert.equal(params.get("location"), "Pune")
  assert.equal(params.get("consultation_mode"), "video")
  assert.equal(params.get("min_experience"), "5")
  assert.equal(params.get("verified_only"), "true")
  assert.equal(params.get("limit"), "20")
  assert.equal(params.get("offset"), "40")
})

test("verification and consultation labels are human readable", () => {
  assert.equal(verificationLabel("VERIFIED"), "Verified")
  assert.equal(verificationLabel("PENDING"), "Pending review")
  assert.equal(verificationLabel("UNVERIFIED"), "Unverified")
  assert.equal(consultationModeLabel("video"), "Video call")
  assert.equal(consultationModeLabel("in-person"), "In person")
})

test("initials never fabricates a name and experienceLabel handles null", () => {
  assert.equal(initials(null), "?")
  assert.equal(initials("  "), "?")
  assert.equal(initials("Asha Rao"), "AR")
  assert.equal(experienceLabel(null), "Experience not stated")
  assert.equal(experienceLabel(1), "1 year experience")
  assert.equal(experienceLabel(6), "6 years experience")
})
