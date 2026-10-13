import { useCallback, useEffect, useState } from "react"

import { ApiError, api } from "@/lib/api"
import type { StatusResponse } from "@/lib/types"

export interface StatusState {
  phase: "idle" | "loading" | "ok" | "error"
  data: StatusResponse | null
  error: string | null
}

export function useStatus() {
  const [state, setState] = useState<StatusState>({ phase: "idle", data: null, error: null })

  const refresh = useCallback(async () => {
    setState((prev) => ({ ...prev, phase: "loading" }))
    try {
      const data = await api.get<StatusResponse>("/status")
      setState({ phase: "ok", data, error: null })
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Unexpected error contacting the backend."
      setState({ phase: "error", data: null, error: message })
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { state, refresh }
}