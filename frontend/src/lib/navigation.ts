import {
  ClipboardList,
  FileText,
  Gavel,
  LayoutDashboard,
  MessageSquare,
  Settings,
  ShieldCheck,
  Upload,
  Users,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import type { UserRole } from "@/lib/roles"

export interface NavItem {
  label: string
  icon: LucideIcon
  to: string
  end?: boolean
  roles: UserRole[]
  comingSoon?: boolean
}

export interface NavSection {
  label: string
  items: NavItem[]
}

const ALL_ROLES: UserRole[] = ["individual", "company", "lawyer", "admin"]

/**
 * Single source of truth for dashboard navigation. Each item declares the roles
 * that may see it, so `navigationForRole` can shape the sidebar per workspace.
 * Items marked `comingSoon` render as disabled placeholders for future roles.
 */
export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", icon: LayoutDashboard, to: "/dashboard", end: true, roles: ALL_ROLES },
    ],
  },
  {
    label: "Documents",
    items: [
      { label: "Upload Documents", icon: Upload, to: "/dashboard/upload", roles: ALL_ROLES },
      { label: "My Documents", icon: FileText, to: "/dashboard/documents", roles: ALL_ROLES },
      {
        label: "Analysis Reports",
        icon: ClipboardList,
        to: "/dashboard/reports",
        roles: ALL_ROLES,
      },
    ],
  },
  {
    label: "Workspace",
    items: [
      {
        label: "Find Legal Help",
        icon: Gavel,
        to: "/dashboard/legal-help",
        roles: ["individual", "company"],
      },
      {
        label: "My Cases",
        icon: Gavel,
        to: "/dashboard/cases",
        roles: ["lawyer"],
        comingSoon: true,
      },
      { label: "Messages", icon: MessageSquare, to: "/dashboard/messages", roles: ALL_ROLES },
      { label: "Settings", icon: Settings, to: "/dashboard/settings", roles: ALL_ROLES },
    ],
  },
  {
    label: "Administration",
    items: [
      {
        label: "Team & Roles",
        icon: Users,
        to: "/dashboard/team",
        roles: ["company", "lawyer", "admin"],
        comingSoon: true,
      },
      {
        label: "Audit Log",
        icon: ShieldCheck,
        to: "/dashboard/audit",
        roles: ["admin"],
        comingSoon: true,
      },
    ],
  },
]

export function navigationForRole(role: UserRole): NavSection[] {
  return NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => item.roles.includes(role)),
  })).filter((section) => section.items.length > 0)
}

/** Best-effort page title for the shell header, based on the active route. */
export function findNavItemLabel(pathname: string): string {
  if (pathname.startsWith("/dashboard/analyses")) {
    return "Analysis Reports"
  }

  let label = "Dashboard"
  let best = -1
  for (const section of NAV_SECTIONS) {
    for (const item of section.items) {
      const matches = item.end
        ? pathname === item.to
        : pathname === item.to || pathname.startsWith(`${item.to}/`)
      if (matches && item.to.length > best) {
        best = item.to.length
        label = item.label
      }
    }
  }
  return label
}
