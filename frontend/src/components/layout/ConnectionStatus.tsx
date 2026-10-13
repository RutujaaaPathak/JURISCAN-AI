import { Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { useHealth } from "@/hooks/useHealth"

export function ConnectionStatus({ compact = false }: { compact?: boolean }) {
  const { state, refresh } = useHealth()

  if (state.phase === "loading" || state.phase === "idle") {
    return (
      <Badge variant="outline" className="gap-1.5">
        <Loader2 className="size-3 animate-spin" aria-hidden="true" />
        {compact ? "Checking" : "Checking backend…"}
      </Badge>
    )
  }

  if (state.phase === "error") {
    return (
      <button type="button" onClick={() => void refresh()} title={state.error ?? undefined}>
        <Badge variant="destructive" className="gap-1.5">
          <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
          {compact ? "Offline" : "Backend unreachable"}
        </Badge>
      </button>
    )
  }

  return (
    <Badge variant="success" className="gap-1.5">
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {compact ? "Online" : `Connected · ${state.data?.environment ?? "ok"}`}
    </Badge>
  )
}