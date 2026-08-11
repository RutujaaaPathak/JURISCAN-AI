import { Scale } from "lucide-react"

import type { ReactNode } from "react"

interface MainLayoutProps {
  children: ReactNode
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
          <a href="/" className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Scale className="size-4" aria-hidden="true" />
            </span>
            <span className="text-base font-semibold tracking-tight">
              JurisScan-AI
            </span>
          </a>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground sm:flex">
            <a href="#" className="transition-colors hover:text-foreground">
              Documents
            </a>
            <a href="#" className="transition-colors hover:text-foreground">
              Analysis
            </a>
            <a href="#" className="transition-colors hover:text-foreground">
              Reports
            </a>
          </nav>
        </div>
      </header>

      <main className="flex flex-1 flex-col">{children}</main>

      <footer className="border-t border-border">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4 text-sm text-muted-foreground sm:px-6">
          <span>&copy; {new Date().getFullYear()} JurisScan-AI</span>
          <span>Legal document auditing and contract analysis</span>
        </div>
      </footer>
    </div>
  )
}
