import { ApiError, api, API_BASE_URL } from "@/lib/api"
import type {
  ApiErrorBody,
  DeleteAllResult,
  DocumentDetail,
  DocumentListResponse,
  OverviewStats,
} from "@/lib/types"

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

export const DOCUMENTS_CHANGED_EVENT = "juriscan:documents-changed"

export function deleteDocument(id: number | string): Promise<void> {
  return api.delete<void>(`/documents/${id}`)
}

export function deleteAllDocuments(): Promise<DeleteAllResult> {
  return api.delete<DeleteAllResult>("/documents")
}

export function uploadDocument(
  file: File,
  title?: string,
  onProgress?: (percent: number) => void,
  force = false,
): Promise<DocumentDetail> {
  const form = new FormData()
  form.append("file", file)
  if (title && title.trim()) {
    form.append("title", title.trim())
  }
  if (force) {
    form.append("force", "true")
  }
  return api.upload<DocumentDetail>("/documents", form, { onProgress })
}

export async function downloadAnalysisReport(
  documentId: number | string,
): Promise<Blob> {
  const url = `${API_BASE_URL}/documents/${documentId}/report`
  let response: Response
  try {
    response = await fetch(url, { headers: { Accept: "application/pdf" } })
  } catch (error) {
    throw new ApiError(
      `Unable to reach the backend at ${API_BASE_URL}.`,
      0,
      "network_error",
      error,
    )
  }

  if (!response.ok) {
    const isJson = response.headers.get("content-type")?.includes("application/json")
    const payload = (isJson ? await response.json().catch(() => null) : null) as
      | ApiErrorBody
      | null
    throw new ApiError(
      payload?.error?.message ?? `Request failed with status ${response.status}.`,
      response.status,
      payload?.error?.code ?? "request_failed",
      payload?.error?.details,
    )
  }
  return response.blob()
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
