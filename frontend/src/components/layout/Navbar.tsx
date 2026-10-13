import { LayoutDashboard, LogOut, Menu, X } from "lucide-react"
import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"

import { Brand } from "@/components/layout/Brand"
import { ConnectionStatus } from "@/components/layout/ConnectionStatus"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth"
import { ROLE_META, dashboardPathForRole } from "@/lib/roles"

const links = [
  { to: "/", label: "Home", end: true },
  { to: "/dashboard", label: "Dashboard", end: false },
  { to: "/#features", label: "Features", end: false },
]

function AuthActions({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      <Button asChild variant="outline" size="sm" className="btn-dark-secondary h-8 px-3.5 text-xs font-medium">
        <Link to="/login" onClick={onNavigate}>
          Log in
        </Link>
      </Button>
      <Button asChild size="sm" className="btn-gold-primary h-8 px-4 text-xs font-semibold">
        <Link to="/signup" onClick={onNavigate}>
          Sign up
        </Link>
      </Button>
    </>
  )
}

function AccountMenu() {
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
        className="flex items-center gap-2 rounded-lg border border-border py-1 pr-2.5 pl-1 text-sm transition-colors hover:bg-muted"
      >
        <span className="flex size-7 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
          {initial}
        </span>
        <span className="max-w-[9rem] truncate">{label}</span>
      </button>

      {open ? (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
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
                navigate(dashboardPathForRole(user.role))
              }}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors hover:bg-muted"
            >
              <LayoutDashboard className="size-4" aria-hidden="true" />
              Dashboard
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
              Sign out
            </button>
          </div>
        </>
      ) : null}
    </div>
  )
}

export function Navbar() {
  const [open, setOpen] = useState(false)
  const { user, status, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const authenticated = status === "authenticated" && user !== null

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.07] bg-[#070b16]/75 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
        <Brand />

        <nav className="hidden items-center gap-7 md:flex">
          {links.map((link) => {
            const isActive =
              link.to === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(link.to)
            return (
              <Link
                key={link.label}
                to={link.to}
                className={cn(
                  "text-sm transition-colors",
                  isActive
                    ? "font-medium text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {link.label}
              </Link>
            )
          })}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <ConnectionStatus compact />
          <ThemeToggle />
          {authenticated ? <AccountMenu /> : <AuthActions />}
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <button
            type="button"
            className="inline-flex size-9 items-center justify-center rounded-lg border border-border transition-colors hover:bg-muted"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X className="size-4" aria-hidden="true" /> : <Menu className="size-4" aria-hidden="true" />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-border md:hidden">
          <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-4 sm:px-6">
            {links.map((link) => (
              <Link
                key={link.label}
                to={link.to}
                className="text-sm text-muted-foreground"
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ))}

            {authenticated && user ? (
              <div className="flex flex-col gap-3 border-t border-border pt-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium">{user.full_name ?? "Account"}</span>
                  <span className="text-xs text-muted-foreground">{user.email}</span>
                </div>
                <Button
                  size="sm"
                  onClick={() => {
                    setOpen(false)
                    navigate(dashboardPathForRole(user.role))
                  }}
                >
                  <LayoutDashboard className="size-4" aria-hidden="true" />
                  Dashboard
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setOpen(false)
                    logout()
                    navigate("/")
                  }}
                >
                  <LogOut className="size-4" aria-hidden="true" />
                  Sign out
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-3 border-t border-border pt-3">
                <AuthActions onNavigate={() => setOpen(false)} />
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <ConnectionStatus compact />
            </div>
          </div>
        </div>
      ) : null}
    </header>
  )
}
