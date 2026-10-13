import { useCallback, useEffect, useState } from "react"

import { ApiError } from "@/lib/api"

export type AsyncPhase = "idle" | "loading" | "ok" | "error"

export interface AsyncState<T> {
  phase: AsyncPhase
  data: T | null
  error: string | null
  errorStatus: number | null
  errorCode: string | null
  lastUpdated: Date | null
}

const initialState = <T,>(): AsyncState<T> => ({
  phase: "idle",
  data: null,
  error: null,
  errorStatus: null,
  errorCode: null,
  lastUpdated: null,
})

export function useAsync<T>(loader: () => Promise<T>) {
  const [state, setState] = useState<AsyncState<T>>(initialState<T>())
  const [reloadToken, setReloadToken] = useState(0)

  const refresh = useCallback(() => setReloadToken((token) => token + 1), [])

  useEffect(() => {
    let active = true
    setState((previous) => ({ ...previous, phase: "loading" }))
    loader()
      .then((data) => {
        if (!active) return
        setState({
          phase: "ok",
          data,
          error: null,
          errorStatus: null,
          errorCode: null,
          lastUpdated: new Date(),
        })
      })
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof ApiError) {
          setState({
            phase: "error",
            data: null,
            error: error.message,
            errorStatus: error.status,
            errorCode: error.code,
            lastUpdated: new Date(),
          })
        } else {
          setState({
            phase: "error",
            data: null,
            error: "An unexpected error occurred.",
            errorStatus: null,
            errorCode: null,
            lastUpdated: new Date(),
          })
        }
      })
    return () => {
      active = false
    }
  }, [loader, reloadToken])

  return { state, refresh }
}
