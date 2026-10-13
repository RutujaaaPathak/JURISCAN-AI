export interface HealthResponse {
  status: string
  app: string
  environment: string
}

export interface StatusResponse {
  status: string
  app: string
  environment: string
  database: string
  database_details: Record<string, unknown> | null
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
  }
}

export interface DocumentSummary {
  id: number
  title: string
  filename: string
  file_type: string
  status: string
  page_count: number | null
  word_count: number | null
  language: string | null
  extracted_at: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  analysis_id: number | null
  analysis_status: string | null
  model_name: string | null
  risk_score: number | null
  risk_level: string | null
  finding_count: number
  high_risk_count: number
}

export interface ClauseRead {
  id: number
  document_id: number
  clause_number: number
  heading: string | null
  text: string
  start_offset: number | null
  end_offset: number | null
  page_number: number | null
  clause_type: string | null
  risk_level: string | null
  label?: string | null
  level?: number
  parent_id?: number | null
  created_at: string
  updated_at: string
}

export interface RiskFindingRead {
  id: number
  analysis_id: number
  clause_id: number | null
  rule_code: string | null
  severity: string
  title: string
  description: string
  recommendation: string | null
  citation: string | null
  clause_number: number | null
  clause_heading: string | null
  clause_page: number | null
  clause_label?: string | null
  clause_level?: number | null
  created_at: string
  updated_at: string
}

export interface AnalysisRead {
  id: number
  document_id: number
  model_name: string
  status: string
  risk_score: number | null
  summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  findings: RiskFindingRead[]
}

export interface DocumentPage {
  page_number: number
  start_offset: number
  end_offset: number
}

export interface DocumentDetail extends DocumentSummary {
  text_content: string | null
  pages: DocumentPage[]
  clauses: ClauseRead[]
  analysis: AnalysisRead | null
}

export interface DocumentListResponse {
  items: DocumentSummary[]
  total: number
}

export interface OverviewStats {
  total_documents: number
  processed: number
  processing: number
  failed: number
  avg_risk_score: number
  high_risk_findings: number
  risk_distribution: Record<string, number>
  category_counts: { category: string; count: number }[]
  upload_trend: { date: string; count: number }[]
}

export interface CaseDocumentSummary {
  id: number
  document_id: number
  title: string
  filename: string
  file_type: string
  status: string
  risk_score: number | null
  risk_level: string | null
  shared_by_user_id: number | null
  created_at: string
  updated_at: string
}

export interface CaseDecisionRead {
  id: number
  lawyer_id: number
  lawyer_name: string | null
  decision: string
  reason: string | null
  message: string | null
  created_at: string
  updated_at: string
}

export interface CaseActivityRead {
  id: number
  action: string
  detail: string | null
  actor_user_id: number | null
  actor_name: string | null
  created_at: string
  updated_at: string
}

export interface CaseNoteRead {
  id: number
  body: string
  author_user_id: number | null
  author_name: string | null
  created_at: string
  updated_at: string
}

export interface CaseSummary {
  id: number
  title: string
  category: string
  summary: string
  jurisdiction: string | null
  urgency: string
  consultation_method: string | null
  budget: string | null
  contact_preference: string | null
  client_reference: string | null
  status: string
  posted_by_user_id: number
  posted_by_name: string | null
  assigned_lawyer_id: number | null
  assigned_lawyer_name: string | null
  document_count: number
  decision_count: number
  my_decision: string | null
  deadline: string | null
  created_at: string
  updated_at: string
  accepted_at: string | null
  completed_at: string | null
}

export interface CaseDetail extends CaseSummary {
  documents: CaseDocumentSummary[]
  decisions: CaseDecisionRead[]
  activities: CaseActivityRead[]
  notes: CaseNoteRead[]
}

export interface CaseListResponse {
  items: CaseSummary[]
  total: number
}

export interface MyCasesResponse {
  active: CaseSummary[]
  completed: CaseSummary[]
  pending: CaseSummary[]
  declined: CaseSummary[]
}

export interface LawyerOverview {
  available_cases: number
  pending_requests: number
  active_cases: number
  completed_cases: number
  total_handled: number
  unread_messages: number
  case_status_distribution: Record<string, number>
  case_category_distribution: { category: string; count: number }[]
}

export interface LawyerProfile {
  id: number
  user_id: number
  full_name: string | null
  bar_registration_number: string | null
  jurisdiction: string | null
  years_experience: number | null
  practice_areas: string[]
  languages: string[]
  location: string | null
  bio: string | null
  consultation_modes: string[]
  fee_structure: string | null
  photo_url: string | null
  availability: string | null
  verification_status: string
  verification_notes: string | null
  profile_complete: boolean
  created_at: string
  updated_at: string
}

export interface LawyerDirectoryEntry {
  user_id: number
  full_name: string | null
  jurisdiction: string | null
  years_experience: number | null
  practice_areas: string[]
  languages: string[]
  location: string | null
  bio: string | null
  consultation_modes: string[]
  fee_structure: string | null
  availability: string | null
  photo_url: string | null
  verification_status: string
  profile_complete: boolean
}

export interface LawyerDirectoryResponse {
  items: LawyerDirectoryEntry[]
  total: number
}

export interface CaseMessage {
  id: number
  sender_user_id: number | null
  sender_name: string | null
  body: string
  read_at: string | null
  created_at: string
  updated_at: string
}

export interface CaseMessageList {
  items: CaseMessage[]
  unread: number
}

export interface CaseClarificationMessage {
  id: number
  lawyer_id: number
  sender_user_id: number | null
  sender_name: string | null
  body: string
  read_at: string | null
  created_at: string
  updated_at: string
}

export interface CaseClarificationThread {
  lawyer_id: number
  lawyer_name: string | null
  unread: number
  items: CaseClarificationMessage[]
}

export interface CaseClarificationThreads {
  threads: CaseClarificationThread[]
}

export interface CaseFeeProposal {
  id: number
  proposed_by_user_id: number | null
  proposed_by_name: string | null
  amount: string
  currency: string
  note: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface CaseAppointment {
  id: number
  proposed_by_user_id: number | null
  proposed_by_name: string | null
  scheduled_at: string
  duration_minutes: number | null
  mode: string | null
  location: string | null
  notes: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface ClientOverview {
  submitted_cases: number
  open_requests: number
  active_matters: number
  completed_matters: number
  upcoming_consultations: number
  unread_messages: number
  case_status_distribution: Record<string, number>
  case_category_distribution: { category: string; count: number }[]
}

export interface NotificationItem {
  id: string
  kind: string
  title: string
  detail: string | null
  case_id: number | null
  created_at: string
}