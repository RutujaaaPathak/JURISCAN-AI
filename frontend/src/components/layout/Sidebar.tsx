import { FileText, LayoutDashboard, Settings, Upload } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { NavLink } from "react-router-dom"

import { cn } from "@/lib/utils"

interface NavItem {
  label: string
  icon: LucideIcon
  to: string
  end?: boolean
}

const items: NavItem[] = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/dashboard", end: true },
  { label: "Upload", icon: Upload, to: "/dashboard/upload" },
  { label: "Documents", icon: FileText, to: "/dashboard/documents" },
  { label: "Settings", icon: Settings, to: "/dashboard/settings" },
]

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex h-full flex-col gap-1 p-3">
      {items.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.label}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Icon className="size-4" aria-hidden="true" />
            {item.label}
          </NavLink>
        )
      })}
    </nav>
  )
}
