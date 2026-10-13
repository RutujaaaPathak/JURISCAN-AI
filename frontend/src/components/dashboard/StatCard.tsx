import type { LucideIcon } from "lucide-react"

import { Card } from "@/components/ui/card"
import type { Tone } from "@/lib/tones"
import { TONE_SURFACE } from "@/lib/tones"
import { cn } from "@/lib/utils"

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  label: string
  value: string | number
  hint?: string
  icon?: LucideIcon
  tone?: Tone
}) {
  return (
    <Card className="gap-3 p-5 transition-all hover:border-amber-400/25 hover:shadow-lg">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-muted-foreground">{label}</span>
        {Icon ? (
          <span
            className={cn(
              "flex size-8 items-center justify-center rounded-lg",
              TONE_SURFACE[tone],
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
          </span>
        ) : null}
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-2xl font-semibold tracking-tight tabular-nums">{value}</span>
        {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
      </div>
    </Card>
  )
}
