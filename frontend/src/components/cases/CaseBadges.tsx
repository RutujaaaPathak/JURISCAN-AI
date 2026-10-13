import { Badge } from "@/components/ui/badge"
import { caseStatusLabel, decisionLabel, urgencyLabel, urgencyTone } from "@/lib/caseFilters"

export function UrgencyBadge({ value }: { value: string }) {
  const tone = urgencyTone(value)
  const variant = tone === "destructive" ? "destructive" : tone === "warning" ? "warning" : "outline"
  return <Badge variant={variant}>{urgencyLabel(value)}</Badge>
}

export function CaseStatusBadge({ status }: { status: string }) {
  const variant =
    status === "COMPLETED" || status === "CLOSED"
      ? "success"
      : status === "ASSIGNED"
        ? "default"
        : "outline"
  return <Badge variant={variant}>{caseStatusLabel(status)}</Badge>
}

export function DecisionBadge({ decision }: { decision: string | null }) {
  if (!decision) {
    return <span className="text-xs text-muted-foreground">No action yet</span>
  }
  const variant =
    decision === "ACCEPT" ? "success" : decision === "REJECT" ? "destructive" : "warning"
  return <Badge variant={variant}>{decisionLabel(decision)}</Badge>
}
