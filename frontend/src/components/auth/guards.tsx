import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"

import { Spinner } from "@/components/ui/spinner"
import { useAuth } from "@/lib/auth"
import type { UserRole } from "@/lib/roles"

function FullPageLoader() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center gap-2 text-sm text-muted-foreground">
      <Spinner />
      Checking your session…
    </div>
  )
}

/** Blocks anonymous visitors, sending them to sign in first. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === "loading") {
    return <FullPageLoader />
  }
  if (status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

/** Keeps signed-in users out of the login/sign-up pages. */
export function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { status } = useAuth()

  if (status === "loading") {
    return <FullPageLoader />
  }
  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}

/**
 * Restricts a route to specific roles, redirecting other signed-in users to
 * their own dashboard. This is presentation-level defence; the backend still
 * enforces authorization against the authenticated role.
 */
export function RequireRole({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const { user } = useAuth()

  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (!roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />
  }
  return <>{children}</>
}
