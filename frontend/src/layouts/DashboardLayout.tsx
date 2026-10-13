import { Menu, X } from "lucide-react"
import { useState } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { Brand } from "@/components/layout/Brand"
import { ConnectionStatus } from "@/components/layout/ConnectionStatus"
import { Sidebar } from "@/components/layout/Sidebar"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { Badge } from "@/components/ui/badge"
import { useRole } from "@/context/RoleContext"
import { findNavItemLabel } from "@/lib/navigation"
import { ROLE_META } from "@/lib/roles"

export function DashboardLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { role } = useRole()
  const { pathname } = useLocation()
  const title = findNavItemLabel(pathname, role)

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex md:flex-col">
        <div className="flex h-16 items-center border-b border-sidebar-border px-4">
          <Brand to="/dashboard" />
        </div>
        <Sidebar />
      </aside>

      {drawerOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute top-0 left-0 h-full w-72 max-w-[85vw] border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-2xl">
            <div className="flex h-16 items-center justify-between border-b border-sidebar-border px-4">
              <Brand to="/dashboard" />
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => setDrawerOpen(false)}
                className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <Sidebar onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-md sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              aria-label="Open navigation"
              onClick={() => setDrawerOpen(true)}
              className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
            >
              <Menu className="size-4" aria-hidden="true" />
            </button>
            <div className="flex min-w-0 items-center gap-2.5">
              <span className="truncate text-sm font-semibold tracking-tight">{title}</span>
              <Badge
                variant="secondary"
                className="hidden shrink-0 border border-primary/15 bg-primary/10 text-primary sm:inline-flex"
              >
                {ROLE_META[role].label} workspace
              </Badge>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <ConnectionStatus compact />
            <ThemeToggle />
          </div>
        </header>

        <main className="bg-app-sheen flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
