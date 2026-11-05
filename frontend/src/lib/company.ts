import { api, downloadBlob } from "@/lib/api"
import type { CompanyRole } from "@/lib/auth"

export type { CompanyRole }
export type InvitationStatus = "PENDING" | "ACCEPTED" | "REVOKED" | "EXPIRED"

export interface CompanyProfile {
  id: number
  name: string
}

export interface TeamMemberRead {
  user_id: number
  full_name: string | null
  email: string
  company_role: CompanyRole
  account_status: "ACTIVE" | "INACTIVE"
  joined_at: string
  is_self: boolean
}

export interface TeamMemberListResponse {
  items: TeamMemberRead[]
  total: number
}

export interface TeamOverview {
  company: CompanyProfile
  total_members: number
  active_members: number
  pending_invitations: number
  role_counts: Record<string, number>
}

export interface InvitationRead {
  id: number
  email: string
  company_role: CompanyRole
  status: InvitationStatus
  invited_by_name: string | null
  created_at: string
  expires_at: string
  accepted_at: string | null
  is_expired: boolean
}

export interface InvitationListResponse {
  items: InvitationRead[]
  total: number
}

export interface InvitationCreateResponse {
  invitation: InvitationRead
  email_sent: boolean
  development_invitation_token: string | null
  development_accept_url: string | null
}

export interface InvitationPreview {
  company_name: string
  email: string
  company_role: CompanyRole
  expires_at: string
  status: InvitationStatus
  is_expired: boolean
  account_exists: boolean
}

export interface InvitationAcceptRequest {
  token: string
  password: string
  full_name?: string
}

export interface AuditReportSummary {
  document_id: number
  document_title: string
  filename: string
  file_type: string
  analysis_id: number | null
  model_name: string | null
  analysis_status: string | null
  report_status: "READY" | "PENDING" | "FAILED" | "NOT_GENERATED" | "COMPLETED" | "PROCESSING" | "UPLOADED"
  audit_date: string | null
  risk_score: number | null
  risk_level: string | null
  safety_score: number | null
  finding_count: number
  high_risk_count: number
  error_message: string | null
}

export interface AuditFinding {
  id: number
  analysis_id: number
  clause_id: number | null
  rule_code: string | null
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  title: string
  description: string
  recommendation: string | null
  citation: string | null
  clause_number: number | null
  clause_heading: string | null
  clause_page: number | null
  clause_label: string | null
  clause_level: number | null
  created_at: string
  updated_at: string
}

export interface AuditReportDetail extends AuditReportSummary {
  analysis_summary: string | null
  clause_count: number
  findings: AuditFinding[]
}

export interface AuditActivity {
  document_id: number
  document_title: string
  event: string
  report_status: string
  risk_level: string | null
  risk_score: number | null
  occurred_at: string
}

export interface AuditReportOverview {
  total_reports: number
  ready_reports: number
  failed_reports: number
  high_risk_reports: number
  medium_risk_reports: number
  low_risk_reports: number
  requiring_attention: number
  avg_risk_score: number
  recent_activity: AuditActivity[]
}

export interface AuditReportListResponse {
  items: AuditReportSummary[]
  total: number
}

export interface AuditReportFilterParams {
  q?: string
  risk_level?: string
  report_status?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

// -----------------------------------------------------------------------------
// Audit Reports API
// -----------------------------------------------------------------------------

export async function getAuditOverview(): Promise<AuditReportOverview> {
  return api.get<AuditReportOverview>("/company/audit-reports/overview")
}

export async function listAuditReports(
  params?: AuditReportFilterParams,
): Promise<AuditReportListResponse> {
  const query = new URLSearchParams()
  if (params?.q?.trim()) query.set("q", params.q.trim())
  if (params?.risk_level && params.risk_level !== "ALL") query.set("risk_level", params.risk_level)
  if (params?.report_status && params.report_status !== "ALL") query.set("report_status", params.report_status)
  if (params?.date_from) query.set("date_from", params.date_from)
  if (params?.date_to) query.set("date_to", params.date_to)
  if (params?.limit) query.set("limit", String(params.limit))
  if (params?.offset) query.set("offset", String(params.offset))

  const qs = query.toString()
  return api.get<AuditReportListResponse>(`/company/audit-reports${qs ? `?${qs}` : ""}`)
}

export async function getAuditReportDetail(documentId: number): Promise<AuditReportDetail> {
  return api.get<AuditReportDetail>(`/company/audit-reports/${documentId}`)
}

export async function downloadAuditReportPdf(documentId: number, filename?: string): Promise<void> {
  await downloadBlob(
    `/company/audit-reports/${documentId}/report`,
    filename ?? `juriscan-audit-${documentId}.pdf`,
  )
}

// -----------------------------------------------------------------------------
// Team Management API
// -----------------------------------------------------------------------------

export async function getTeamOverview(): Promise<TeamOverview> {
  return api.get<TeamOverview>("/company/team/overview")
}

export async function listTeamMembers(): Promise<TeamMemberListResponse> {
  return api.get<TeamMemberListResponse>("/company/team")
}

export async function updateMemberRole(
  memberId: number,
  companyRole: CompanyRole,
): Promise<TeamMemberRead> {
  return api.patch<TeamMemberRead>(`/company/team/members/${memberId}/role`, {
    company_role: companyRole,
  })
}

export async function removeTeamMember(memberId: number): Promise<void> {
  return api.delete(`/company/team/members/${memberId}`)
}

export async function listInvitations(): Promise<InvitationListResponse> {
  return api.get<InvitationListResponse>("/company/team/invitations")
}

export async function createInvitation(payload: {
  email: string
  company_role: CompanyRole
}): Promise<InvitationCreateResponse> {
  return api.post<InvitationCreateResponse>("/company/team/invitations", payload)
}

export async function revokeInvitation(invitationId: number): Promise<InvitationRead> {
  return api.post<InvitationRead>(`/company/team/invitations/${invitationId}/revoke`)
}

export async function previewInvitation(token: string): Promise<InvitationPreview> {
  return api.get<InvitationPreview>(`/company/invitations/preview?token=${encodeURIComponent(token)}`)
}

export async function acceptInvitation(payload: InvitationAcceptRequest): Promise<unknown> {
  return api.post("/company/invitations/accept", payload)
}

