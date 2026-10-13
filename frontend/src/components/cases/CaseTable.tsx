import { Paperclip } from "lucide-react"
import type { ReactNode } from "react"

import { CaseStatusBadge, UrgencyBadge } from "@/components/cases/CaseBadges"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { caseCategoryLabel } from "@/lib/caseFilters"
import { formatDate } from "@/lib/format"
import type { CaseSummary } from "@/lib/types"

export function CaseTable({
  cases,
  empty,
  renderAction,
}: {
  cases: CaseSummary[]
  empty: ReactNode
  renderAction?: (item: CaseSummary) => ReactNode
}) {
  if (cases.length === 0) {
    return <>{empty}</>
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Matter</TableHead>
            <TableHead className="hidden md:table-cell">Category</TableHead>
            <TableHead>Urgency</TableHead>
            <TableHead className="hidden sm:table-cell">Status</TableHead>
            <TableHead className="hidden lg:table-cell">Client</TableHead>
            <TableHead className="hidden lg:table-cell">Posted</TableHead>
            {renderAction ? <TableHead className="text-right">Action</TableHead> : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {cases.map((item) => (
            <TableRow key={item.id}>
              <TableCell className="max-w-[22rem]">
                <div className="flex flex-col gap-0.5">
                  <span className="truncate text-sm font-medium">{item.title}</span>
                  <span className="flex items-center gap-2 text-xs text-muted-foreground">
                    {item.document_count > 0 ? (
                      <span className="inline-flex items-center gap-1">
                        <Paperclip className="size-3" aria-hidden="true" />
                        {item.document_count}
                      </span>
                    ) : null}
                    {item.jurisdiction ? <span>{item.jurisdiction}</span> : null}
                  </span>
                </div>
              </TableCell>
              <TableCell className="hidden md:table-cell">
                {caseCategoryLabel(item.category)}
              </TableCell>
              <TableCell>
                <UrgencyBadge value={item.urgency} />
              </TableCell>
              <TableCell className="hidden sm:table-cell">
                <CaseStatusBadge status={item.status} />
              </TableCell>
              <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                {item.posted_by_name ?? "—"}
              </TableCell>
              <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                {formatDate(item.created_at)}
              </TableCell>
              {renderAction ? (
                <TableCell className="text-right">{renderAction(item)}</TableCell>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
