/**
 * Workspace roles.
 *
 * Authentication is not implemented yet, so the frontend only carries the
 * concept of an "active workspace role" used to shape navigation. No session,
 * credentials or identity are fabricated here. When auth lands, the role can be
 * sourced from the authenticated user and fed into `RoleProvider`.
 */
export type UserRole = "individual" | "company" | "lawyer" | "admin"

export interface RoleMeta {
  id: UserRole
  label: string
  description: string
}

export const ROLE_META: Record<UserRole, RoleMeta> = {
  individual: {
    id: "individual",
    label: "Individual",
    description: "Personal contract review workspace for solo users.",
  },
  company: {
    id: "company",
    label: "Company",
    description: "Shared workspace for in-house legal and procurement teams.",
  },
  lawyer: {
    id: "lawyer",
    label: "Lawyer",
    description: "Client and case workspace for external counsel.",
  },
  admin: {
    id: "admin",
    label: "Admin",
    description: "Platform administration and governance workspace.",
  },
}

export const USER_ROLES: UserRole[] = ["individual", "company", "lawyer", "admin"]

export const DEFAULT_ROLE: UserRole = "individual"

export function isUserRole(value: string | null | undefined): value is UserRole {
  return value !== null && value !== undefined && value in ROLE_META
}
