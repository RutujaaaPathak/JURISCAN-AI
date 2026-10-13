import { createContext, useContext, useMemo, useState } from "react"
import type { ReactNode } from "react"

import type { UserRole } from "@/lib/roles"
import { DEFAULT_ROLE } from "@/lib/roles"

interface RoleContextValue {
  role: UserRole
  setRole: (role: UserRole) => void
}

const RoleContext = createContext<RoleContextValue | null>(null)

/**
 * Holds the active workspace role for the dashboard shell. This is deliberately
 * not an authentication provider: it defaults to the individual workspace and
 * exists so Company, Lawyer and Admin dashboards can plug in later.
 */
export function RoleProvider({
  children,
  initialRole = DEFAULT_ROLE,
}: {
  children: ReactNode
  initialRole?: UserRole
}) {
  const [role, setRole] = useState<UserRole>(initialRole)
  const value = useMemo(() => ({ role, setRole }), [role])

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>
}

export function useRole() {
  const context = useContext(RoleContext)
  if (!context) {
    throw new Error("useRole must be used within a RoleProvider")
  }
  return context
}
