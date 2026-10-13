import { NavLink } from "react-router-dom"

import { Select } from "@/components/ui/select"
import { useRole } from "@/context/RoleContext"
import { navigationForRole } from "@/lib/navigation"
import { ROLE_META, USER_ROLES, isUserRole } from "@/lib/roles"
import { cn } from "@/lib/utils"

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { role, setRole } = useRole()
  const sections = navigationForRole(role)

  return (
    <nav className="flex h-full flex-col gap-5 overflow-y-auto p-3" aria-label="Dashboard">
      {sections.map((section) => (
        <div key={section.label} className="flex flex-col gap-1">
          <p className="px-3 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
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
                  className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground/60"
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
        </div>
      ))}

      <div className="mt-auto flex flex-col gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2.5">
        <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          Workspace
        </p>
        <Select
          aria-label="Preview workspace"
          value={role}
          onChange={(event) => {
            const next = event.target.value
            if (isUserRole(next)) {
              setRole(next)
            }
          }}
        >
          {USER_ROLES.map((value) => (
            <option key={value} value={value}>
              {ROLE_META[value].label}
            </option>
          ))}
        </Select>
        <p className="text-xs text-muted-foreground">{ROLE_META[role].description}</p>
        <p className="text-[10px] leading-snug text-muted-foreground">
          UI preview only — switches navigation to preview each workspace. Not sign-in and does not
          grant access to any data.
        </p>
      </div>
    </nav>
  )
}
