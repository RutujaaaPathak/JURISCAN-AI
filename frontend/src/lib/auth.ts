/**
 * Authentication client.
 *
 * This module owns the session token store, the auth API calls, the React
 * context and the `useAuth` hook. The role used to shape the UI always comes
 * from the authenticated user returned by the backend — never from a
 * URL parameter or client-side selection.
 */

import { createContext, useContext } from "react"

import { api, setAuthToken } from "@/lib/api"
import type { UserRole } from "@/lib/roles"

export interface AuthUser {
  id: number
  email: string
  username: string
  full_name: string | null
  role: UserRole
  organization_name: string | null
  is_active: boolean
}

/** Roles a visitor may self-register for. Admin is provisioned operationally. */
export const PUBLIC_ROLES: UserRole[] = ["individual", "company", "lawyer"]

export function isPublicRole(value: string | null | undefined): value is "individual" | "company" | "lawyer" {
  return value === "individual" || value === "company" || value === "lawyer"
}

export interface RegisterPayload {
  role: "individual" | "company" | "lawyer"
  email: string
  password: string
  full_name: string
  organization_name?: string
  bar_registration_number?: string
  jurisdiction?: string
  years_experience?: number
  practice_areas?: string[]
  languages?: string[]
  location?: string
  bio?: string
}

interface AuthResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

export async function registerAccount(payload: RegisterPayload): Promise<AuthUser> {
  const data = await api.post<AuthResponse>("/auth/register", payload)
  setAuthToken(data.access_token)
  return data.user
}

export async function loginAccount(email: string, password: string): Promise<AuthUser> {
  const data = await api.post<AuthResponse>("/auth/login", { email, password })
  setAuthToken(data.access_token)
  return data.user
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return api.get<AuthUser>("/auth/me")
}

export interface AuthContextValue {
  user: AuthUser | null
  status: "loading" | "authenticated" | "anonymous"
  login: (email: string, password: string) => Promise<AuthUser>
  register: (payload: RegisterPayload) => Promise<AuthUser>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
