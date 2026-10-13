import { NavLink } from "react-router-dom"

import { useRole } from "@/context/RoleContext"
import { navigationForRole } from "@/lib/navigation"
import { ROLE_META } from "@/lib/roles"
import { cn } from "@/lib/utils"

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { role } = useRole()
  const sections = navigationForRole(role)

  return (
    <nav className="flex h-full flex-col gap-5 overflow-y-auto p-3" aria-label="Dashboard">
      {sections.map((section) => (
        <div key={section.label} className="flex flex-col gap-1">
          <p className="px-3 text-[11px] font-semibold tracking-wider text-muted-foreground/70 uppercase">
            {section.label}
          </p>
          {section.items.map((item) => {
            const Icon = item.icon

            if (item.comingSoon) {
              return (
                <span
                  key={item.label}
                  aria-disabled="true"
                  title="Coming soon"
                  className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground/60"
                >
                  <Icon className="size-4" aria-hidden="true" />
                  {item.label}
                  <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                    Soon
                  </span>
                </span>
              )
            }

            return (
              <NavLink
                key={item.label}
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring/50",
                    isActive
                      ? "bg-primary/15 text-primary border border-primary/30 shadow-[0_0_15px_-3px_rgba(229,193,88,0.2)] font-semibold"
                      : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground hover:border-white/5 border border-transparent",
                  )
                }
              >
                <Icon className="size-4" aria-hidden="true" />
                {item.label}
              </NavLink>
            )
          })}
        </div>
      ))}

      <div className="mt-auto flex flex-col gap-1.5 rounded-xl border border-sidebar-border bg-sidebar-accent/40 px-3 py-2.5">
        <p className="text-[11px] font-semibold tracking-wider text-muted-foreground/70 uppercase">
          Workspace
        </p>
        <p className="text-sm font-medium">{ROLE_META[role].label}</p>
        <p className="text-xs text-muted-foreground">{ROLE_META[role].description}</p>
      </div>
    </nav>
  )
}
