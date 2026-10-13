import {
  Bell,
  Building2,
  CalendarDays,
  ClipboardList,
  FileText,
  Gavel,
  Inbox,
  LayoutDashboard,
  MessageSquare,
  Settings,
  ShieldCheck,
  Upload,
  UserCog,
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
 * Items marked `comingSoon` render as disabled placeholders.
 *
 * Navigation shaping is presentation only and is not an access-control
 * boundary; the backend enforces role checks independently.
 */
export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Overview",
    items: [
      {
        label: "Dashboard",
        icon: LayoutDashboard,
        to: "/dashboard/client",
        end: true,
        roles: ["individual"],
      },
      {
        label: "Overview",
        icon: LayoutDashboard,
        to: "/dashboard/company",
        end: true,
        roles: ["company"],
      },
      {
        label: "Dashboard",
        icon: LayoutDashboard,
        to: "/dashboard/lawyer",
        end: true,
        roles: ["lawyer"],
      },
      {
        label: "Dashboard",
        icon: LayoutDashboard,
        to: "/dashboard",
        end: true,
        roles: ["admin"],
      },
    ],
  },
  {
    label: "Cases",
    items: [
      {
        label: "Available Cases",
        icon: Inbox,
        to: "/dashboard/available-cases",
        roles: ["lawyer"],
      },
      {
        label: "My Cases",
        icon: Gavel,
        to: "/dashboard/my-cases",
        roles: ["lawyer"],
      },
      {
        label: "Find a Lawyer",
        icon: Users,
        to: "/dashboard/legal-help",
        roles: ["individual"],
      },
      {
        label: "Post a Case",
        icon: Gavel,
        to: "/dashboard/post-case",
        roles: ["individual"],
      },
      {
        label: "My Legal Cases",
        icon: Gavel,
        to: "/dashboard/legal-cases",
        roles: ["individual"],
      },
    ],
  },
  {
    label: "Documents",
    items: [
      { label: "Upload Documents", icon: Upload, to: "/dashboard/upload", roles: ["individual", "lawyer", "admin"] },
      { label: "My Documents", icon: FileText, to: "/dashboard/documents", roles: ["individual", "lawyer", "admin"] },
      { label: "Company Documents", icon: Building2, to: "/dashboard/documents", roles: ["company"] },
      { label: "Upload Contract", icon: Upload, to: "/dashboard/upload", roles: ["company"] },
      {
        label: "Analysis Reports",
        icon: ClipboardList,
        to: "/dashboard/reports",
        roles: ALL_ROLES,
      },
    ],
  },
  {
    label: "Communication",
    items: [
      { label: "Messages", icon: MessageSquare, to: "/dashboard/messages", roles: ["individual", "lawyer", "admin"] },
      { label: "Calendar", icon: CalendarDays, to: "/dashboard/calendar", roles: ["lawyer"] },
      { label: "Notifications", icon: Bell, to: "/dashboard/notifications", roles: ["lawyer", "individual"] },
    ],
  },
  {
    label: "Compliance",
    items: [
      {
        label: "Audit Reports",
        icon: ShieldCheck,
        to: "/dashboard/audit-reports",
        roles: ["company", "admin"],
        comingSoon: true,
      },
    ],
  },
  {
    label: "Administration",
    items: [
      {
        label: "Team Management",
        icon: Users,
        to: "/dashboard/team",
        roles: ["company", "admin"],
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
  {
    label: "Account",
    items: [
      { label: "Lawyer Profile", icon: UserCog, to: "/dashboard/profile", roles: ["lawyer"] },
      { label: "Settings", icon: Settings, to: "/dashboard/settings", roles: ALL_ROLES },
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
export function findNavItemLabel(pathname: string, role?: UserRole): string {
  if (pathname.startsWith("/dashboard/analyses")) {
    return "Analysis Reports"
  }
  if (pathname.startsWith("/dashboard/cases/")) {
    return "Case details"
  }

  const sections = role ? navigationForRole(role) : NAV_SECTIONS
  let label = "Dashboard"
  let best = -1
  for (const section of sections) {
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
