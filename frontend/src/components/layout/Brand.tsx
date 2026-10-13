import { Scale } from "lucide-react"
import { Link } from "react-router-dom"

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <span className="flex size-8 items-center justify-center rounded-lg bg-linear-to-br from-primary to-[color-mix(in_oklch,var(--primary),var(--chart-2)_55%)] text-primary-foreground shadow-sm ring-1 ring-primary/30 ring-inset">
        <Scale className="size-4" aria-hidden="true" />
      </span>
      <span className="text-base font-semibold tracking-tight">JurisScan-AI</span>
    </Link>
  )
}
