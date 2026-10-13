import { api } from "@/lib/api"
import { buildCaseListSearch } from "@/lib/caseFilters"
import type { CaseListQuery } from "@/lib/caseFilters"
import type {
  CaseDetail,
  CaseListResponse,
  LawyerOverview,
  LawyerProfile,
  MyCasesResponse,
} from "@/lib/types"

export interface CreateCasePayload {
  title: string
  category: string
  summary: string
  jurisdiction?: string | null
  urgency?: string
  consultation_method?: string | null
  budget?: string | null
  contact_preference?: string | null
  client_reference?: string | null
  deadline?: string | null
  document_ids?: number[]
}

export interface LawyerProfilePayload {
  full_name?: string | null
  bar_registration_number?: string | null
  jurisdiction?: string | null
  years_experience?: number | null
  practice_areas?: string[]
  languages?: string[]
  location?: string | null
  bio?: string | null
  consultation_modes?: string[]
  fee_structure?: string | null
  photo_url?: string | null
  availability?: string | null
}

export function listCases(query: CaseListQuery = {}): Promise<CaseListResponse> {
  const search = buildCaseListSearch(query)
  return api.get<CaseListResponse>(`/cases${search ? `?${search}` : ""}`)
}

export function getCase(id: number | string): Promise<CaseDetail> {
  return api.get<CaseDetail>(`/cases/${id}`)
}

export function createCase(payload: CreateCasePayload): Promise<CaseDetail> {
  return api.post<CaseDetail>("/cases", payload)
}

export function acceptCase(id: number | string): Promise<CaseDetail> {
  return api.post<CaseDetail>(`/cases/${id}/accept`)
}

export function rejectCase(id: number | string, reason: string): Promise<CaseDetail> {
  return api.post<CaseDetail>(`/cases/${id}/reject`, { reason })
}

export function requestCaseInfo(id: number | string, message: string): Promise<CaseDetail> {
  return api.post<CaseDetail>(`/cases/${id}/request-info`, { message })
}

export function completeCase(id: number | string): Promise<CaseDetail> {
  return api.post<CaseDetail>(`/cases/${id}/complete`)
}

export function addCaseNote(id: number | string, body: string): Promise<CaseDetail> {
  return api.post<CaseDetail>(`/cases/${id}/notes`, { body })
}

export function getMyCases(): Promise<MyCasesResponse> {
  return api.get<MyCasesResponse>("/cases/mine")
}

export function getLawyerOverview(): Promise<LawyerOverview> {
  return api.get<LawyerOverview>("/cases/overview")
}

export function getLawyerProfile(): Promise<LawyerProfile> {
  return api.get<LawyerProfile>("/lawyer/profile")
}

export function updateLawyerProfile(payload: LawyerProfilePayload): Promise<LawyerProfile> {
  return api.put<LawyerProfile>("/lawyer/profile", payload)
}

export function submitLawyerVerification(): Promise<LawyerProfile> {
  return api.post<LawyerProfile>("/lawyer/profile/verification")
}
