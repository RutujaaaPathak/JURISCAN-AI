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