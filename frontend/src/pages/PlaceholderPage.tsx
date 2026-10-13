import { Info } from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { EmptyState } from "@/components/common/States"
import { Card, CardContent } from "@/components/ui/card"

export function PlaceholderPage({
  title,
  description,
  icon,
  notice,
  emptyTitle,
  emptyDescription,
}: {
  title: string
  description: string
  icon: LucideIcon
  notice: string
  emptyTitle: string
  emptyDescription: string
}) {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>

      <Card>
        <CardContent className="flex items-start gap-3 py-1 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>{notice}</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <EmptyState icon={icon} title={emptyTitle} description={emptyDescription} />
        </CardContent>
      </Card>
    </div>
  )
}
