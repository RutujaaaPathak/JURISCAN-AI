import { AlertTriangle, CheckCircle2, Clock, Loader2, ShieldAlert } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { RiskLevel } from "@/lib/risk"
import { RISK_META } from "@/lib/risk"
import { cn } from "@/lib/utils"

export function SeverityBadge({ level, className }: { level: RiskLevel; className?: string }) {
  const meta = RISK_META[level]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        meta.badge,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", meta.dot)} aria-hidden="true" />
      {meta.label}
    </span>
  )
}

const STATUS_META: Record<
  string,
  {
    label: string
    variant: "success" | "warning" | "secondary" | "outline" | "destructive"
    icon: typeof CheckCircle2
    spin?: boolean
  }
> = {
  PROCESSED: { label: "Analyzed", variant: "success", icon: CheckCircle2 },
  COMPLETED: { label: "Completed", variant: "success", icon: CheckCircle2 },
  PROCESSING: { label: "Processing", variant: "secondary", icon: Loader2, spin: true },
  PENDING: { label: "Pending", variant: "outline", icon: Clock },
  FAILED: { label: "Failed", variant: "destructive", icon: AlertTriangle },
}

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? {
    label: status,
    variant: "outline" as const,
    icon: ShieldAlert,
  }
  const Icon = meta.icon
  return (
    <Badge variant={meta.variant}>
      <Icon className={cn("size-3", meta.spin && "animate-spin")} aria-hidden="true" />
      {meta.label}
    </Badge>
  )
}
