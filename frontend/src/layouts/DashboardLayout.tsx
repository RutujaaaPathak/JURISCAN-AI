import { LogOut, Menu, Settings, X } from "lucide-react"
import { useState } from "react"
import { Outlet, useLocation, useNavigate } from "react-router-dom"

import { Brand } from "@/components/layout/Brand"
import { ConnectionStatus } from "@/components/layout/ConnectionStatus"
import { Sidebar } from "@/components/layout/Sidebar"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { Badge } from "@/components/ui/badge"
import { useRole } from "@/context/RoleContext"
import { useAuth } from "@/lib/auth"
import { findNavItemLabel } from "@/lib/navigation"
import { ROLE_META } from "@/lib/roles"

function DashboardAccountMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  if (!user) return null
  const label = user.full_name ?? user.email
  const initial = label.charAt(0).toUpperCase()

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-2 rounded-lg border border-border py-1 pr-1.5 pl-1 text-sm transition-colors hover:bg-muted sm:pr-2.5"
      >
        <span className="flex size-7 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
          {initial}
        </span>
        <span className="hidden max-w-[9rem] truncate sm:inline">{label}</span>
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            role="menu"
            className="absolute right-0 z-50 mt-2 w-60 rounded-xl border border-border bg-card p-2 shadow-lg"
          >
            <div className="px-2.5 py-2">
              <p className="truncate text-sm font-medium">{user.full_name ?? "Account"}</p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
              <Badge variant="secondary" className="mt-2">
                {ROLE_META[user.role].label}
              </Badge>
            </div>
            <div className="my-1 h-px bg-border" />
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                navigate("/dashboard/settings")
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors hover:bg-muted"
            >
              <Settings className="size-4" aria-hidden="true" />
              Settings
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                logout()
                navigate("/")
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-destructive transition-colors hover:bg-destructive/10"
            >
              <LogOut className="size-4" aria-hidden="true" />
              Log out
            </button>
          </div>
        </>
      ) : null}
    </div>
  )
}

export function DashboardLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { role } = useRole()
  const { pathname } = useLocation()
  const title = findNavItemLabel(pathname, role)

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to content
      </a>
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
            <DashboardAccountMenu />
          </div>
        </header>

        <main id="main-content" className="bg-app-sheen flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
