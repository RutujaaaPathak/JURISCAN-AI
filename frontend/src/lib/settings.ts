import { api } from "@/lib/api"
import type { UserRole } from "@/lib/roles"

export type SeverityLevel = "low" | "medium" | "high" | "critical"
export type AnalysisModel = "rules" | "heuristic" | "legal-bert"

/**
 * Settings as returned by the authenticated `/settings` endpoint. Account
 * identity fields (`email`, `full_name`, `role`, `organization_name`) come from
 * the signed-in user; the rest are per-user preferences persisted server-side.
 */
export interface UserSettings {
  email: string
  full_name: string | null
  role: UserRole
  organization_name: string | null
  jurisdiction: string | null
  min_severity: SeverityLevel
  analysis_model: AnalysisModel
  auto_analyze: boolean
  notify_email_digest: boolean
  notify_high_risk: boolean
  notify_weekly_report: boolean
  updated_at: string
}

/** Only mutable fields. Email is intentionally absent (account identity). */
export interface UserSettingsUpdate {
  full_name?: string | null
  organization_name?: string | null
  jurisdiction?: string | null
  min_severity?: SeverityLevel
  analysis_model?: AnalysisModel
  auto_analyze?: boolean
  notify_email_digest?: boolean
  notify_high_risk?: boolean
  notify_weekly_report?: boolean
}

export function getSettings(): Promise<UserSettings> {
  return api.get<UserSettings>("/settings")
}

export function updateSettings(payload: UserSettingsUpdate): Promise<UserSettings> {
  return api.put<UserSettings>("/settings", payload)
}
