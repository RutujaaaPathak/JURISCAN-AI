import { FileText, Filter, Loader2, RefreshCw, Search, Trash2 } from "lucide-react"
import { useCallback, useDeferredValue, useState } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge, StatusBadge } from "@/components/analysis/RiskBadges"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useToast } from "@/components/ui/toast"
import { useAsync } from "@/hooks/useAsync"
import { ApiError } from "@/lib/api"
import {
  DOCUMENTS_CHANGED_EVENT,
  deleteAllDocuments,
  deleteDocument,
  listDocuments,
} from "@/lib/documents"
import { formatDate, formatFileType } from "@/lib/format"
import type { RiskLevel } from "@/lib/risk"
import { RISK_LEVELS, RISK_META, riskLevelFromScoreOrNull, toRiskLevel } from "@/lib/risk"
import type { DocumentSummary } from "@/lib/types"

const statuses = ["PROCESSED", "PROCESSING", "PENDING", "FAILED"] as const
const fileTypes = ["pdf", "docx", "txt"] as const

export function DocumentsPage() {
  const [query, setQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [riskFilter, setRiskFilter] = useState("all")
  const [pendingDelete, setPendingDelete] = useState<DocumentSummary | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteAllOpen, setDeleteAllOpen] = useState(false)
  const [deleteAllConfirm, setDeleteAllConfirm] = useState("")
  const [deletingAll, setDeletingAll] = useState(false)
  const { toast } = useToast()
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

  const handleDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteDocument(pendingDelete.id)
      toast({
        title: "Document deleted",
        description: `"${pendingDelete.title}" and its analysis were removed.`,
        variant: "success",
      })
      setPendingDelete(null)
      void refresh()
      window.dispatchEvent(new CustomEvent(DOCUMENTS_CHANGED_EVENT))
    } catch (error) {
      toast({
        title: "Could not delete document",
        description:
          error instanceof ApiError ? error.message : "An unexpected error occurred.",
        variant: "destructive",
      })
    } finally {
      setDeleting(false)
    }
  }

  const closeDeleteAll = () => {
    if (deletingAll) return
    setDeleteAllOpen(false)
    setDeleteAllConfirm("")
  }

  const handleDeleteAll = async () => {
    if (deleteAllConfirm !== "DELETE ALL" || deletingAll) return
    setDeletingAll(true)
    try {
      const { deleted } = await deleteAllDocuments()
      toast({
        title: "All documents deleted",
        description: `${deleted} document${deleted === 1 ? "" : "s"} and associated data were removed.`,
        variant: "success",
      })
      setDeleteAllOpen(false)
      setDeleteAllConfirm("")
      void refresh()
      window.dispatchEvent(new CustomEvent(DOCUMENTS_CHANGED_EVENT))
    } catch (error) {
      toast({
        title: "Could not delete documents",
        description:
          error instanceof ApiError ? error.message : "An unexpected error occurred.",
        variant: "destructive",
      })
    } finally {
      setDeletingAll(false)
    }
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
          <Button
            variant="outline"
            size="sm"
            className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={() => setDeleteAllOpen(true)}
            disabled={state.phase !== "ok" || (state.data?.total ?? 0) === 0}
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Delete All
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
                          <div className="flex items-center justify-end gap-1">
                            {doc.status === "PROCESSED" ? (
                              <Button variant="outline" size="sm" asChild>
                                <Link to={`/dashboard/analyses/${doc.id}`}>View</Link>
                              </Button>
                            ) : (
                              <Button variant="outline" size="sm" disabled>
                                View
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              className="text-muted-foreground hover:text-destructive"
                              aria-label={`Delete ${doc.title}`}
                              onClick={() => setPendingDelete(doc)}
                            >
                              <Trash2 className="size-4" aria-hidden="true" />
                            </Button>
                          </div>
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

      <Dialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setPendingDelete(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete document?</DialogTitle>
            <DialogDescription>
              {pendingDelete
                ? `"${pendingDelete.title}" and its extracted clauses, analysis and findings will be permanently deleted. This action cannot be undone.`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" size="sm" disabled={deleting}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleDelete()}
              disabled={deleting}
            >
              {deleting ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Trash2 className="size-4" aria-hidden="true" />
              )}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleteAllOpen}
        onOpenChange={(open) => {
          if (!open) closeDeleteAll()
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete all documents?</DialogTitle>
            <DialogDescription>
              This will permanently delete all documents in the current
              application database, including their associated clauses, analysis
              results, and findings. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 flex flex-col gap-2">
            <Label htmlFor="delete-all-confirm">
              Type <span className="font-mono font-semibold text-destructive">DELETE ALL</span> to
              confirm
            </Label>
            <Input
              id="delete-all-confirm"
              value={deleteAllConfirm}
              onChange={(event) => setDeleteAllConfirm(event.target.value)}
              placeholder="DELETE ALL"
              autoComplete="off"
              autoFocus
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" size="sm" disabled={deletingAll}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleDeleteAll()}
              disabled={deleteAllConfirm !== "DELETE ALL" || deletingAll}
            >
              {deletingAll ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Trash2 className="size-4" aria-hidden="true" />
              )}
              Delete All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
