import { Link } from "react-router-dom"

import { Brand } from "@/components/layout/Brand"

export function Footer() {
  return (
    <footer className="border-t border-white/[0.07] bg-[#070b16]/90 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-12 sm:px-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-sm">
            <Brand />
            <p className="mt-3 text-sm text-muted-foreground">
              Structured, explainable contract review. Legal document auditing for individuals,
              companies and legal teams.
            </p>
          </div>
          <nav className="flex flex-wrap gap-x-12 gap-y-6 text-sm">
            <div className="flex flex-col gap-2">
              <span className="font-medium text-foreground">Product</span>
              <Link to="/" className="text-muted-foreground transition-colors hover:text-foreground">
                Home
              </Link>
              <Link
                to="/#features"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                Features
              </Link>
              <Link
                to="/dashboard"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                Dashboard
              </Link>
            </div>
            <div className="flex flex-col gap-2">
              <span className="font-medium text-foreground">Legal</span>
              <Link
                to="/privacy"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                Privacy Policy
              </Link>
              <Link
                to="/terms"
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                Terms of Service
              </Link>
            </div>
          </nav>
        </div>
        <div className="flex flex-col gap-2 border-t border-white/[0.06] pt-6 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span>&copy; {new Date().getFullYear()} JurisScan-AI. All rights reserved.</span>
          <span>JurisScan-AI does not provide legal advice.</span>
        </div>
      </div>
    </footer>
  )
}
