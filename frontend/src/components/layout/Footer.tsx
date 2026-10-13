import { Link } from "react-router-dom"

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <span>&copy; {new Date().getFullYear()} JurisScan-AI</span>
        <nav className="flex items-center gap-4">
          <Link to="/" className="transition-colors hover:text-foreground">
            Home
          </Link>
          <Link to="/dashboard" className="transition-colors hover:text-foreground">
            Dashboard
          </Link>
          <span className="hidden sm:inline">Legal document auditing and contract analysis</span>
        </nav>
      </div>
    </footer>
  )
}