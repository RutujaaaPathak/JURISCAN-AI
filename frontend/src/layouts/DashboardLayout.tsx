import { Menu, X } from "lucide-react"
import { useState } from "react"
import { Outlet, useLocation } from "react-router-dom"

import { Brand } from "@/components/layout/Brand"
import { ConnectionStatus } from "@/components/layout/ConnectionStatus"
import { Sidebar } from "@/components/layout/Sidebar"
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
      <aside className="hidden w-64 shrink-0 border-r border-border md:flex md:flex-col">
        <div className="flex h-16 items-center border-b border-border px-4">
          <Brand to="/dashboard" />
        </div>
        <Sidebar />
      </aside>

      {drawerOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute top-0 left-0 h-full w-64 border-r border-border bg-background">
            <div className="flex h-16 items-center justify-between border-b border-border px-4">
              <Brand to="/dashboard" />
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => setDrawerOpen(false)}
                className="rounded-md p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <Sidebar onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Open navigation"
              onClick={() => setDrawerOpen(true)}
              className="inline-flex size-9 items-center justify-center rounded-md border border-border md:hidden"
            >
              <Menu className="size-4" aria-hidden="true" />
            </button>
            <span className="text-sm font-medium">{title}</span>
            <Badge variant="outline" className="hidden sm:inline-flex">
              {ROLE_META[role].label} workspace
            </Badge>
          </div>
          <ConnectionStatus compact />
        </header>

        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
