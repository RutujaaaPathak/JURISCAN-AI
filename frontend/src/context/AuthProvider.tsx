import { useCallback, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"

import { ApiError, getAuthToken, setAuthToken } from "@/lib/api"
import {
  AuthContext,
  fetchCurrentUser,
  loginAccount,
  logoutAccount,
  registerAccount,
} from "@/lib/auth"
import type { AuthUser, RegisterPayload } from "@/lib/auth"

type AuthStatus = "loading" | "authenticated" | "anonymous"

const SESSION_REVALIDATE_INTERVAL_MS = 60_000

/**
 * Resolves the session on mount (if a token is stored) and exposes login,
 * register and logout. The authenticated backend user is the single source of
 * truth for the active role.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] = useState<AuthStatus>(() =>
    getAuthToken() ? "loading" : "anonymous",
  )

  const clearSession = useCallback(() => {
    setAuthToken(null)
    setUser(null)
    setStatus("anonymous")
  }, [])

  useEffect(() => {
    if (!getAuthToken()) {
      setStatus("anonymous")
      return
    }
    let active = true
    fetchCurrentUser()
      .then((current) => {
        if (!active) return
        setUser(current)
        setStatus("authenticated")
      })
      .catch(() => {
        if (!active) return
        clearSession()
      })
    return () => {
      active = false
    }
  }, [clearSession])

  const login = useCallback(async (email: string, password: string) => {
    const current = await loginAccount(email, password)
    setUser(current)
    setStatus("authenticated")
    return current
  }, [])

  const register = useCallback(async (payload: RegisterPayload) => {
    const created = await registerAccount(payload)
    setUser(created)
    setStatus("authenticated")
    return created
  }, [])

  const logout = useCallback(async () => {
    try {
      // Server-side revocation must run before the bearer token is discarded.
      await logoutAccount()
    } catch {
      // A network/server failure must not leave the UI in an authenticated
      // state, but the token would then remain valid until its expiry.
    } finally {
      clearSession()
    }
  }, [clearSession])

  const refresh = useCallback(async () => {
    if (!getAuthToken()) return
    try {
      const current = await fetchCurrentUser()
      setUser(current)
      setStatus("authenticated")
    } catch (error) {
      // A revoked/expired token is terminal; keep the current session only on a
      // transient failure so an offline blip does not sign the user out.
      if (error instanceof ApiError && error.status === 401) {
        clearSession()
      }
    }
  }, [clearSession])

  useEffect(() => {
    if (status !== "authenticated") return
    const revalidate = () => {
      if (getAuthToken()) void refresh()
    }
    const timer = window.setInterval(
      revalidate,
      SESSION_REVALIDATE_INTERVAL_MS,
    )
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") revalidate()
    }
    document.addEventListener("visibilitychange", onVisibilityChange)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener("visibilitychange", onVisibilityChange)
    }
  }, [status, refresh])

  const value = useMemo(
    () => ({ user, status, login, register, logout, refresh }),
    [user, status, login, register, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
