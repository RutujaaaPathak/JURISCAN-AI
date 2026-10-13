import { Clock3 } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDateTime } from "@/lib/format"
import type { Tone } from "@/lib/tones"
import { TONE_SURFACE } from "@/lib/tones"
import { cn } from "@/lib/utils"

export interface ActivityItem {
  id: string
  title: string
  description?: string
  timestamp: string
  icon: LucideIcon
  tone?: Tone
}

export function ActivityFeed({ items, empty }: { items: ActivityItem[]; empty?: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent activity</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          (empty ?? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No activity has been recorded yet.
            </p>
          ))
        ) : (
          <ol className="flex flex-col">
            {items.map((item) => {
              const Icon = item.icon
              return (
                <li
                  key={item.id}
                  className="flex items-start gap-3 border-b border-white/[0.06] py-3 first:pt-0 last:border-b-0 last:pb-0"
                >
                  <span
                    className={cn(
                      "flex size-8 shrink-0 items-center justify-center rounded-full",
                      TONE_SURFACE[item.tone ?? "default"],
                    )}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{item.title}</p>
                    {item.description ? (
                      <p className="truncate text-xs text-muted-foreground">{item.description}</p>
                    ) : null}
                  </div>
                  <span className="flex shrink-0 items-center gap-1 text-xs whitespace-nowrap text-muted-foreground">
                    <Clock3 className="size-3" aria-hidden="true" />
                    {formatDateTime(item.timestamp)}
                  </span>
                </li>
              )
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}
