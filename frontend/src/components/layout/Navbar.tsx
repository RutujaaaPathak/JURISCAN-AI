import { Menu, X } from "lucide-react"
import { useState } from "react"
import { Link, NavLink } from "react-router-dom"

import { Brand } from "@/components/layout/Brand"
import { ConnectionStatus } from "@/components/layout/ConnectionStatus"
import { ThemeToggle } from "@/components/layout/ThemeToggle"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const links = [
  { to: "/", label: "Home" },
  { to: "/dashboard", label: "Dashboard" },
]

export function Navbar() {
  const [open, setOpen] = useState(false)

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      "text-sm transition-colors hover:text-foreground",
      isActive ? "font-medium text-foreground" : "text-muted-foreground",
    )

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
        <Brand />

        <nav className="hidden items-center gap-6 md:flex">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className={linkClass} end={link.to === "/"}>
              {link.label}
            </NavLink>
          ))}
          <a href="/#features" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Features
          </a>
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <ConnectionStatus compact />
          <ThemeToggle />
          <Button asChild size="sm">
            <Link to="/dashboard">Open dashboard</Link>
          </Button>
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
              <NavLink
                key={link.to}
                to={link.to}
                className={linkClass}
                end={link.to === "/"}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </NavLink>
            ))}
            <a
              href="/#features"
              className="text-sm text-muted-foreground"
              onClick={() => setOpen(false)}
            >
              Features
            </a>
            <div className="flex items-center justify-between pt-2">
              <ConnectionStatus compact />
              <Button asChild size="sm">
                <Link to="/dashboard" onClick={() => setOpen(false)}>
                  Open dashboard
                </Link>
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </header>
  )
}
