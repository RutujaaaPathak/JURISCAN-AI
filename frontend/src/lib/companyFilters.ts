import type { CompanyRole } from "@/lib/auth"
import type {
  AuditReportFilterParams,
  AuditReportSummary,
  TeamMemberRead,
} from "@/lib/company"

export const COMPANY_ROLE_META: Record<
  CompanyRole,
  { label: string; description: string; rank: number }
> = {
  COMPANY_ADMIN: {
    label: "Company Admin",
    description: "Full company management, team administration and workspace access.",
    rank: 1,
  },
  MANAGER: {
    label: "Manager",
    description: "Manage documents, reports, and oversee team activity.",
    rank: 2,
  },
  MEMBER: {
    label: "Member",
    description: "Upload and analyze company contracts, view shared documents.",
    rank: 3,
  },
  VIEWER: {
    label: "Viewer",
    description: "Read-only access to company documents and audit reports.",
    rank: 4,
  },
}

export function formatCompanyRole(role: string | null | undefined): string {
  if (!role) return "Member"
  return COMPANY_ROLE_META[role as CompanyRole]?.label ?? role
}

export function buildAuditSearch(params: AuditReportFilterParams): Record<string, string> {
  const result: Record<string, string> = {}
  if (params.q?.trim()) result.q = params.q.trim()
  if (params.risk_level && params.risk_level !== "ALL") result.risk_level = params.risk_level
  if (params.report_status && params.report_status !== "ALL") result.report_status = params.report_status
  if (params.date_from) result.date_from = params.date_from
  if (params.date_to) result.date_to = params.date_to
  return result
}

export function filterTeamMembers(
  members: TeamMemberRead[],
  query: string,
  roleFilter?: string,
): TeamMemberRead[] {
  const q = query.trim().toLowerCase()
  return members.filter((member) => {
    if (roleFilter && roleFilter !== "ALL" && member.company_role !== roleFilter) {
      return false
    }
    if (!q) return true
    const nameMatch = member.full_name?.toLowerCase().includes(q)
    const emailMatch = member.email.toLowerCase().includes(q)
    return Boolean(nameMatch || emailMatch)
  })
}

export function filterAuditReports(
  reports: AuditReportSummary[],
  query: string,
  riskLevel?: string,
  reportStatus?: string,
): AuditReportSummary[] {
  const q = query.trim().toLowerCase()
  return reports.filter((report) => {
    if (riskLevel && riskLevel !== "ALL" && report.risk_level !== riskLevel) {
      return false
    }
    if (reportStatus && reportStatus !== "ALL" && report.report_status !== reportStatus) {
      return false
    }
    if (!q) return true
    const titleMatch = report.document_title.toLowerCase().includes(q)
    const fileMatch = report.filename.toLowerCase().includes(q)
    return Boolean(titleMatch || fileMatch)
  })
}

