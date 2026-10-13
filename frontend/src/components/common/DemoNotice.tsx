import { FlaskConical } from "lucide-react"

import { DEMO_DATA_NOTICE } from "@/data/demo"
import { cn } from "@/lib/utils"

export function DemoNotice({
  className,
  text = DEMO_DATA_NOTICE,
}: {
  className?: string
  text?: string
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-lg border border-amber-300/70 bg-amber-50 px-3 py-2.5 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/50 dark:text-amber-200",
        className,
      )}
    >
      <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>
        <span className="font-semibold">Demo data.</span> {text}
      </p>
    </div>
  )
}
