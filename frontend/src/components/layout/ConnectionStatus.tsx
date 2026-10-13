import { Loader2 } from "lucide-react"

import { useHealth } from "@/hooks/useHealth"

export function ConnectionStatus({ compact = false }: { compact?: boolean }) {
  const { state, refresh } = useHealth()

  if (state.phase === "loading" || state.phase === "idle") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-card/60 px-2.5 py-1 text-xs text-muted-foreground backdrop-blur-sm">
        <Loader2 className="size-3 animate-spin text-muted-foreground" aria-hidden="true" />
        {compact ? "Checking" : "Checking backend…"}
      </span>
    )
  }

  if (state.phase === "error") {
    return (
      <button
        type="button"
        onClick={() => void refresh()}
        title={state.error ?? undefined}
        className="outline-none"
      >
        <span className="inline-flex items-center gap-1.5 rounded-full border border-destructive/30 bg-destructive/15 px-2.5 py-1 text-xs font-medium text-destructive transition-colors hover:bg-destructive/20">
          <span className="size-1.5 rounded-full bg-destructive shadow-[0_0_6px_rgba(239,68,68,0.6)]" aria-hidden="true" />
          {compact ? "Offline" : "Backend unreachable"}
        </span>
      </button>
    )
  }

  const env = state.data?.environment ?? "development"

  if (compact) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-950/30 px-2.5 py-0.5 text-xs font-medium text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.1)]">
        <span className="size-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(34,197,94,0.8)]" aria-hidden="true" />
        Online
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-amber-400/25 bg-amber-400/10 px-3 py-1 text-xs font-medium text-amber-200/90 shadow-[0_0_12px_rgba(245,158,11,0.1)]">
      <span className="size-1.5 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(245,158,11,0.8)]" aria-hidden="true" />
      Connected • {env}
    </span>
  )
}