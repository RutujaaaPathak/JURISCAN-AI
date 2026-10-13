import { createContext, useContext, useMemo } from "react"
import type { ReactNode } from "react"

import { useAuth } from "@/lib/auth"
import type { UserRole } from "@/lib/roles"
import { DEFAULT_ROLE } from "@/lib/roles"

interface RoleContextValue {
  role: UserRole
}

const RoleContext = createContext<RoleContextValue | null>(null)

/**
 * Exposes the active workspace role for the dashboard shell. The role is
 * sourced from the authenticated user (see AuthProvider); it is not user
 * selectable. Anonymous visitors fall back to the default role, but protected
 * routes never render a dashboard for them.
 */
export function RoleProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const role = user?.role ?? DEFAULT_ROLE
  const value = useMemo(() => ({ role }), [role])

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>
}

export function useRole() {
  const context = useContext(RoleContext)
  if (!context) {
    throw new Error("useRole must be used within a RoleProvider")
  }
  return context
}
