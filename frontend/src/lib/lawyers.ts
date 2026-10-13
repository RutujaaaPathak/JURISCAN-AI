import { api } from "@/lib/api"
import { buildLawyerSearch } from "@/lib/lawyerFilters"
import type { LawyerSearchQuery } from "@/lib/lawyerFilters"
import type { LawyerDirectoryEntry, LawyerDirectoryResponse } from "@/lib/types"

export function listLawyers(
  query: LawyerSearchQuery = {},
): Promise<LawyerDirectoryResponse> {
  const search = buildLawyerSearch(query)
  return api.get<LawyerDirectoryResponse>(`/lawyers${search ? `?${search}` : ""}`)
}

export function getLawyer(userId: number | string): Promise<LawyerDirectoryEntry> {
  return api.get<LawyerDirectoryEntry>(`/lawyers/${userId}`)
}
