import { BookOpen, Lightbulb, TextSearch, Wrench } from "lucide-react"

import { SeverityBadge } from "@/components/analysis/RiskBadges"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import type { RiskFindingRead } from "@/lib/types"
import { RISK_META, toRiskLevel } from "@/lib/risk"

function clauseLabel(finding: RiskFindingRead): string {
  const parts: string[] = []
  if (finding.clause_number !== null) parts.push(`Clause ${finding.clause_number}`)
  if (finding.clause_page !== null) parts.push(`p.${finding.clause_page}`)
  return parts.join(" · ")
}

export function ClauseCard({
  finding,
  clauseText,
  onViewInText,
}: {
  finding: RiskFindingRead
  clauseText?: string | null
  onViewInText?: (clauseId: number) => void
}) {
  const level = toRiskLevel(finding.severity) ?? "low"
  const meta = RISK_META[level]
  const clauseTitle = clauseLabel(finding)
  const clauseId = finding.clause_id

  return (
    <Card className="gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge level={level} />
          <span className="text-sm font-medium">{finding.title}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {clauseTitle ? <span>{clauseTitle}</span> : null}
          {finding.rule_code ? (
            <span className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px]">
              {finding.rule_code}
            </span>
          ) : null}
          {onViewInText && clauseId !== null ? (
            <Button
              variant="ghost"
              size="xs"
              onClick={() => onViewInText(clauseId)}
              aria-label={`View clause ${finding.clause_number ?? ""} in extracted text`}
            >
              <TextSearch aria-hidden="true" />
              View in text
            </Button>
          ) : null}
        </div>
      </div>

      {clauseText ? (
        <blockquote
          className="rounded-r-lg border-l-4 bg-muted/50 px-4 py-3 text-sm italic leading-relaxed"
          style={{ borderLeftColor: meta.hex }}
        >
          {clauseText}
        </blockquote>
      ) : null}

      {finding.clause_heading ? (
        <p className="text-xs text-muted-foreground">Section: {finding.clause_heading}</p>
      ) : null}

      <div className="flex flex-col gap-3">
        <div className="flex gap-2.5">
          <Lightbulb className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div>
            <p className="text-xs font-medium text-muted-foreground">Why it matters</p>
            <p className="text-sm">{finding.description}</p>
          </div>
        </div>
        {finding.recommendation ? (
          <div className="flex gap-2.5">
            <Wrench className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div>
              <p className="text-xs font-medium text-muted-foreground">Recommendation</p>
              <p className="text-sm">{finding.recommendation}</p>
            </div>
          </div>
        ) : null}
      </div>

      {finding.citation ? (
        <div className="flex flex-col gap-1.5 border-t border-border pt-3">
          <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <BookOpen className="size-3.5" aria-hidden="true" />
            Reference
          </p>
          <p className="text-xs text-muted-foreground">{finding.citation}</p>
        </div>
      ) : null}
    </Card>
  )
}
