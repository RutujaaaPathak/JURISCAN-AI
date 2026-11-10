import assert from "node:assert/strict"
import test from "node:test"

import {
  buildAuditSearch,
  filterAuditReports,
  filterTeamMembers,
  formatCompanyRole,
} from "./companyFilters.ts"
import type { AuditReportSummary, TeamMemberRead } from "./company.js"

test("formatCompanyRole formats known roles and falls back safely", () => {
  assert.equal(formatCompanyRole("COMPANY_ADMIN"), "Company Admin")
  assert.equal(formatCompanyRole("MANAGER"), "Manager")
  assert.equal(formatCompanyRole("MEMBER"), "Member")
  assert.equal(formatCompanyRole("VIEWER"), "Viewer")
  assert.equal(formatCompanyRole(null), "Member")
  assert.equal(formatCompanyRole(undefined), "Member")
  assert.equal(formatCompanyRole("CUSTOM_ROLE"), "CUSTOM_ROLE")
})

test("buildAuditSearch strips empty or ALL filters", () => {
  const result = buildAuditSearch({
    q: "  nondisclosure  ",
    risk_level: "ALL",
    report_status: "READY",
    date_from: "2026-01-01",
  })
  assert.deepEqual(result, {
    q: "nondisclosure",
    report_status: "READY",
    date_from: "2026-01-01",
  })
})

test("filterTeamMembers matches by name, email, and role", () => {
  const members: TeamMemberRead[] = [
    {
      user_id: 1,
      full_name: "Sarah Conner",
      email: "sarah@cyberdyne.com",
      company_role: "COMPANY_ADMIN",
      account_status: "ACTIVE",
      joined_at: "2026-01-01T00:00:00Z",
      is_self: true,
    },
    {
      user_id: 2,
      full_name: "John Connor",
      email: "john@cyberdyne.com",
      company_role: "MEMBER",
      account_status: "ACTIVE",
      joined_at: "2026-01-02T00:00:00Z",
      is_self: false,
    },
    {
      user_id: 3,
      full_name: "Kyle Reese",
      email: "kyle@tech.org",
      company_role: "VIEWER",
      account_status: "INACTIVE",
      joined_at: "2026-01-03T00:00:00Z",
      is_self: false,
    },
  ]

  assert.equal(filterTeamMembers(members, "sarah").length, 1)
  assert.equal(filterTeamMembers(members, "cyberdyne").length, 2)
  assert.equal(filterTeamMembers(members, "", "MEMBER").length, 1)
  assert.equal(filterTeamMembers(members, "john", "COMPANY_ADMIN").length, 0)
  assert.equal(filterTeamMembers(members, "", "ALL").length, 3)
})

test("filterAuditReports matches search and status", () => {
  const reports: AuditReportSummary[] = [
    {
      document_id: 101,
      document_title: "Master Services Agreement",
      filename: "msa-2026.pdf",
      file_type: "pdf",
      analysis_id: 1,
      model_name: "juriscan-rules-v1",
      analysis_status: "COMPLETED",
      report_status: "READY",
      audit_date: "2026-01-01T00:00:00Z",
      risk_score: 80,
      risk_level: "CRITICAL",
      safety_score: 20,
      finding_count: 4,
      high_risk_count: 2,
      error_message: null,
    },
    {
      document_id: 102,
      document_title: "Non-Disclosure Agreement",
      filename: "nda.docx",
      file_type: "docx",
      analysis_id: 2,
      model_name: "juriscan-rules-v1",
      analysis_status: "COMPLETED",
      report_status: "READY",
      audit_date: "2026-01-02T00:00:00Z",
      risk_score: 20,
      risk_level: "LOW",
      safety_score: 80,
      finding_count: 1,
      high_risk_count: 0,
      error_message: null,
    },
  ]

  assert.equal(filterAuditReports(reports, "services").length, 1)
  assert.equal(filterAuditReports(reports, "nda.docx").length, 1)
  assert.equal(filterAuditReports(reports, "", "CRITICAL").length, 1)
  assert.equal(filterAuditReports(reports, "", "LOW").length, 1)
  assert.equal(filterAuditReports(reports, "", "ALL", "READY").length, 2)
  assert.equal(filterAuditReports(reports, "", "ALL", "FAILED").length, 0)
})
