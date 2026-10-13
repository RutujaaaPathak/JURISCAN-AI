import { useCallback, useEffect, useState } from "react"

import { ApiError, api } from "@/lib/api"
import type { HealthResponse } from "@/lib/types"

export type HealthPhase = "idle" | "loading" | "ok" | "error"

export interface HealthState {
  phase: HealthPhase
  data: HealthResponse | null
  error: string | null
  lastChecked: Date | null
}

export function useHealth(pollIntervalMs = 15000) {
  const [state, setState] = useState<HealthState>({
    phase: "idle",
    data: null,
    error: null,
    lastChecked: null,
  })

  const refresh = useCallback(async () => {
    setState((prev) => ({ ...prev, phase: "loading" }))
    try {
      const data = await api.get<HealthResponse>("/health")
      setState({ phase: "ok", data, error: null, lastChecked: new Date() })
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Unexpected error contacting the backend."
      setState({ phase: "error", data: null, error: message, lastChecked: new Date() })
    }
  }, [])

  useEffect(() => {
    let active = true
    const run = () => {
      if (active) void refresh()
    }
    run()
    const timer = window.setInterval(run, pollIntervalMs)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [refresh, pollIntervalMs])

  return { state, refresh }
}