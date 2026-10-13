import { Scale } from "lucide-react"
import { Link } from "react-router-dom"

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2.5">
      <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <Scale className="size-4" aria-hidden="true" />
      </span>
      <span className="text-base font-semibold tracking-tight">JurisScan-AI</span>
    </Link>
  )
}