import { useCallback, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"

import { getAuthToken, setAuthToken } from "@/lib/api"
import {
  AuthContext,
  fetchCurrentUser,
  loginAccount,
  registerAccount,
} from "@/lib/auth"
import type { AuthUser, RegisterPayload } from "@/lib/auth"

type AuthStatus = "loading" | "authenticated" | "anonymous"

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
        setAuthToken(null)
        setUser(null)
        setStatus("anonymous")
      })
    return () => {
      active = false
    }
  }, [])

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

  const logout = useCallback(() => {
    setAuthToken(null)
    setUser(null)
    setStatus("anonymous")
  }, [])

  const refresh = useCallback(async () => {
    if (!getAuthToken()) return
    try {
      const current = await fetchCurrentUser()
      setUser(current)
      setStatus("authenticated")
    } catch {
      // Keep the current session on a transient failure; a real expiry is
      // handled when the token is next used or on the next mount.
    }
  }, [])

  const value = useMemo(
    () => ({ user, status, login, register, logout, refresh }),
    [user, status, login, register, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
