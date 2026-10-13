import { api } from "@/lib/api"
import type { DocumentDetail, DocumentListResponse, OverviewStats } from "@/lib/types"

export interface DocumentListParams {
  q?: string
  status?: string
  file_type?: string
  risk_level?: string
  limit?: number
  offset?: number
}

export function listDocuments(params: DocumentListParams = {}): Promise<DocumentListResponse> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return api.get<DocumentListResponse>(`/documents${query ? `?${query}` : ""}`)
}

export function getDocument(id: number | string): Promise<DocumentDetail> {
  return api.get<DocumentDetail>(`/documents/${id}`)
}

export function getOverviewStats(): Promise<OverviewStats> {
  return api.get<OverviewStats>("/stats/overview")
}

export function uploadDocument(
  file: File,
  title?: string,
  onProgress?: (percent: number) => void,
): Promise<DocumentDetail> {
  const form = new FormData()
  form.append("file", file)
  if (title && title.trim()) {
    form.append("title", title.trim())
  }
  return api.upload<DocumentDetail>("/documents", form, { onProgress })
}
