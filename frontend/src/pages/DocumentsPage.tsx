import { FileText, Filter, RefreshCw, Search } from "lucide-react"
import { useCallback, useDeferredValue, useState } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge, StatusBadge } from "@/components/analysis/RiskBadges"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useAsync } from "@/hooks/useAsync"
import { listDocuments } from "@/lib/documents"
import { formatDate, formatFileType } from "@/lib/format"
import type { RiskLevel } from "@/lib/risk"
import { RISK_LEVELS, RISK_META, riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"

const statuses = ["PROCESSED", "PROCESSING", "PENDING", "FAILED"] as const
const fileTypes = ["pdf", "docx", "txt"] as const

export function DocumentsPage() {
  const [query, setQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [riskFilter, setRiskFilter] = useState("all")
  const deferredQuery = useDeferredValue(query)

  const loader = useCallback(
    () =>
      listDocuments({
        q: deferredQuery.trim() || undefined,
        file_type: typeFilter === "all" ? undefined : typeFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
        risk_level: riskFilter === "all" ? undefined : riskFilter,
        limit: 200,
      }),
    [deferredQuery, typeFilter, statusFilter, riskFilter],
  )

  const { state, refresh } = useAsync(loader)

  const hasFilters =
    query !== "" || typeFilter !== "all" || statusFilter !== "all" || riskFilter !== "all"

  const clearFilters = () => {
    setQuery("")
    setTypeFilter("all")
    setStatusFilter("all")
    setRiskFilter("all")
  }

  const items = state.data?.items ?? []

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Document history</h1>
          <p className="text-sm text-muted-foreground">
            Every document uploaded for review, with its current status and risk.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={state.phase === "loading"}>
            <RefreshCw className="size-4" aria-hidden="true" />
            Refresh
          </Button>
          <Button asChild>
            <Link to="/dashboard/upload">Upload document</Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
            Filters
          </CardTitle>
          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Reset
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search title or file…"
              className="pl-9"
              aria-label="Search documents"
            />
          </div>
          <Select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="File type">
            <option value="all">All types</option>
            {fileTypes.map((type) => (
              <option key={type} value={type}>
                {formatFileType(type)}
              </option>
            ))}
          </Select>
          <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Status">
            <option value="all">All statuses</option>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {value.charAt(0) + value.slice(1).toLowerCase()}
              </option>
            ))}
          </Select>
          <Select value={riskFilter} onChange={(event) => setRiskFilter(event.target.value)} aria-label="Risk level">
            <option value="all">All risk levels</option>
            {RISK_LEVELS.map((level: RiskLevel) => (
              <option key={level} value={level.toUpperCase()}>
                {RISK_META[level].label}
              </option>
            ))}
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>
            {state.phase === "ok" ? `${state.data?.total ?? 0} document(s)` : "Documents"}
          </CardTitle>
          {state.lastUpdated && state.phase === "ok" ? (
            <span className="text-xs text-muted-foreground">
              Updated {state.lastUpdated.toLocaleTimeString()}
            </span>
          ) : null}
        </CardHeader>
        <CardContent>
          {state.phase === "loading" || state.phase === "idle" ? (
            <LoadingSkeleton rows={5} />
          ) : state.phase === "error" ? (
            <ErrorState
              title="Could not load documents"
              description={state.error ?? undefined}
              onRetry={() => void refresh()}
            />
          ) : items.length === 0 ? (
            hasFilters ? (
              <EmptyState
                icon={FileText}
                title="No documents match your filters"
                description="Try a different search term or reset the filters."
                action={
                  <Button variant="outline" size="sm" onClick={clearFilters}>
                    Reset filters
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={FileText}
                title="No documents yet"
                description="Upload a PDF, DOCX or TXT contract to run the first rule-based analysis."
                action={
                  <Button asChild size="sm">
                    <Link to="/dashboard/upload">Upload document</Link>
                  </Button>
                }
              />
            )
          ) : (
            <div className="overflow-hidden rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Document</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Risk</TableHead>
                    <TableHead className="hidden lg:table-cell">Findings</TableHead>
                    <TableHead className="hidden lg:table-cell">Uploaded</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((doc) => {
                    const level = toRiskLevel(doc.risk_level) ?? riskLevelFromScoreOrNull(doc.risk_score)
                    return (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="flex items-center gap-2.5">
                            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                              <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">{doc.title}</p>
                              <p className="truncate text-xs text-muted-foreground">{doc.filename}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge variant="outline">{formatFileType(doc.file_type)}</Badge>
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={doc.status} />
                        </TableCell>
                        <TableCell>
                          {level ? (
                            <div className="flex items-center gap-2">
                              <SeverityBadge level={level} />
                              <span className="text-xs text-muted-foreground">
                                {Math.round(doc.risk_score ?? 0)}
                              </span>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                          {doc.finding_count} ({doc.high_risk_count} high)
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                          {formatDate(doc.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          {doc.status === "PROCESSED" ? (
                            <Button variant="outline" size="sm" asChild>
                              <Link to={`/dashboard/analyses/${doc.id}`}>View</Link>
                            </Button>
                          ) : (
                            <Button variant="outline" size="sm" disabled>
                              View
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
