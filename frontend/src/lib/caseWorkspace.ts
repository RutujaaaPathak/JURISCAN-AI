import { api } from "@/lib/api"
import type {
  CaseAppointment,
  CaseClarificationThreads,
  CaseDetail,
  CaseFeeProposal,
  CaseMessageList,
  ClientOverview,
  NotificationItem,
} from "@/lib/types"

/**
 * Client / assigned-lawyer workspace client. Every endpoint here is scoped
 * server-side to the two parties of an assigned case; the UI only reaches them
 * once a case is assigned.
 */

export function getCaseMessages(id: number | string): Promise<CaseMessageList> {
  return api.get<CaseMessageList>(`/cases/${id}/messages`)
}

export function sendCaseMessage(id: number | string, body: string): Promise<CaseMessageList> {
  return api.post<CaseMessageList>(`/cases/${id}/messages`, { body })
}

export function markCaseMessagesRead(id: number | string): Promise<CaseMessageList> {
  return api.post<CaseMessageList>(`/cases/${id}/messages/read`)
}

/**
 * Pre-assignment clarifications. A lawyer may ask the client for information
 * while a case is open; each thread is private to that lawyer and the client.
 * The client supplies `lawyerId` when answering a specific thread.
 */
export function getCaseClarifications(id: number | string): Promise<CaseClarificationThreads> {
  return api.get<CaseClarificationThreads>(`/cases/${id}/clarifications`)
}

export function sendCaseClarification(
  id: number | string,
  message: string,
  lawyerId?: number | null,
): Promise<CaseClarificationThreads> {
  return api.post<CaseClarificationThreads>(`/cases/${id}/clarifications`, {
    message,
    ...(lawyerId != null ? { lawyer_id: lawyerId } : {}),
  })
}

export function markCaseClarificationsRead(
  id: number | string,
  lawyerId?: number | null,
): Promise<CaseClarificationThreads> {
  return api.post<CaseClarificationThreads>(
    `/cases/${id}/clarifications/read`,
    lawyerId != null ? { lawyer_id: lawyerId } : undefined,
  )
}

export interface FeeProposalPayload {
  amount: string
  currency?: string
  note?: string | null
}

export function getCaseFees(id: number | string): Promise<CaseFeeProposal[]> {
  return api.get<CaseFeeProposal[]>(`/cases/${id}/fees`)
}

export function proposeCaseFee(
  id: number | string,
  payload: FeeProposalPayload,
): Promise<CaseFeeProposal[]> {
  return api.post<CaseFeeProposal[]>(`/cases/${id}/fees`, payload)
}

export function acceptCaseFee(
  id: number | string,
  proposalId: number,
): Promise<CaseFeeProposal[]> {
  return api.post<CaseFeeProposal[]>(`/cases/${id}/fees/${proposalId}/accept`)
}

export function declineCaseFee(
  id: number | string,
  proposalId: number,
): Promise<CaseFeeProposal[]> {
  return api.post<CaseFeeProposal[]>(`/cases/${id}/fees/${proposalId}/decline`)
}

export interface AppointmentPayload {
  scheduled_at: string
  duration_minutes?: number | null
  mode?: string | null
  location?: string | null
  notes?: string | null
}

export function getCaseAppointments(id: number | string): Promise<CaseAppointment[]> {
  return api.get<CaseAppointment[]>(`/cases/${id}/appointments`)
}

export function proposeCaseAppointment(
  id: number | string,
  payload: AppointmentPayload,
): Promise<CaseAppointment[]> {
  return api.post<CaseAppointment[]>(`/cases/${id}/appointments`, payload)
}

export function confirmCaseAppointment(
  id: number | string,
  appointmentId: number,
): Promise<CaseAppointment[]> {
  return api.post<CaseAppointment[]>(`/cases/${id}/appointments/${appointmentId}/confirm`)
}

export function cancelCaseAppointment(
  id: number | string,
  appointmentId: number,
): Promise<CaseAppointment[]> {
  return api.post<CaseAppointment[]>(`/cases/${id}/appointments/${appointmentId}/cancel`)
}

export function shareCaseDocument(
  id: number | string,
  documentId: number,
): Promise<CaseDetail> {
  return api.post<CaseDetail>(`/cases/${id}/documents`, { document_id: documentId })
}

export function getClientOverview(): Promise<ClientOverview> {
  return api.get<ClientOverview>("/cases/user-overview")
}

export function getNotifications(): Promise<NotificationItem[]> {
  return api.get<NotificationItem[]>("/notifications")
}
