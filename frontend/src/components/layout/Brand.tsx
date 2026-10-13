import { Scale } from "lucide-react"
import { Link } from "react-router-dom"

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#ebd28b] via-[#cda14d] to-[#996f26] text-[#1a1204] shadow-[inset_0_1px_1px_rgba(255,255,255,0.45),0_2px_8px_rgba(0,0,0,0.35)] ring-1 ring-amber-300/40 transition-transform group-hover:scale-105">
        <Scale className="size-4.5 stroke-[2.2]" aria-hidden="true" />
      </span>
      <span className="text-base font-semibold tracking-tight text-foreground group-hover:text-foreground/90 transition-colors">
        JurisScan-AI
      </span>
    </Link>
  )
}
