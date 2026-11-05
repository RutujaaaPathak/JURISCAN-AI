import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  FileText,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  RotateCcw,
  Upload,
  X,
} from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge } from "@/components/analysis/RiskBadges"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { StatCard } from "@/components/dashboard/StatCard"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useToast } from "@/components/ui/toast"
import {
  downloadAuditReportPdf,
  getAuditOverview,
  getAuditReportDetail,
  listAuditReports,
} from "@/lib/company"
import type {
  AuditReportDetail,
  AuditReportFilterParams,
  AuditReportOverview,
  AuditReportSummary,
} from "@/lib/company"
import { DOCUMENTS_CHANGED_EVENT } from "@/lib/documents"
import { formatDate, formatFileType } from "@/lib/format"
import { toRiskLevel } from "@/lib/risk"

export function AuditReportsPage() {
  const { toast } = useToast()

  // Overview stats state
  const [overview, setOverview] = useState<AuditReportOverview | null>(null)
  const [loadingOverview, setLoadingOverview] = useState(true)

  // Report list state
  const [reports, setReports] = useState<AuditReportSummary[]>([])
  const [loadingReports, setLoadingReports] = useState(true)
  const [reportsError, setReportsError] = useState<string | null>(null)

  // Filter state
  const [search, setSearch] = useState("")
  const [riskFilter, setRiskFilter] = useState("ALL")
  const [statusFilter, setStatusFilter] = useState("ALL")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  // Active detail modal
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null)
  const [detailData, setDetailData] = useState<AuditReportDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  // PDF download loading state per report id
  const [downloadingId, setDownloadingId] = useState<number | null>(null)

  const fetchOverview = useCallback(async () => {
    setLoadingOverview(true)
    try {
      const data = await getAuditOverview()
      setOverview(data)
    } catch {
      // Non-critical, reports list still functions
    } finally {
      setLoadingOverview(false)
    }
  }, [])

  const fetchReports = useCallback(async () => {
    setLoadingReports(true)
    setReportsError(null)
    try {
      const params: AuditReportFilterParams = {
        q: search,
        risk_level: riskFilter,
        report_status: statusFilter,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 100,
      }
      const data = await listAuditReports(params)
      setReports(data.items)
    } catch (err) {
      setReportsError(err instanceof Error ? err.message : "Failed to load audit reports.")
    } finally {
      setLoadingReports(false)
    }
  }, [search, riskFilter, statusFilter, dateFrom, dateTo])

  useEffect(() => {
    void fetchOverview()
  }, [fetchOverview])

  useEffect(() => {
    void fetchReports()
  }, [fetchReports])

  useEffect(() => {
    const handleDocsChanged = () => {
      void fetchOverview()
      void fetchReports()
    }
    window.addEventListener(DOCUMENTS_CHANGED_EVENT, handleDocsChanged)
    return () => {
      window.removeEventListener(DOCUMENTS_CHANGED_EVENT, handleDocsChanged)
    }
  }, [fetchOverview, fetchReports])

  const openReportDetail = async (documentId: number) => {
    setSelectedReportId(documentId)
    setDetailData(null)
    setLoadingDetail(true)
    setDetailError(null)
    try {
      const detail = await getAuditReportDetail(documentId)
      setDetailData(detail)
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : "Could not load report details.")
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleDownloadPdf = async (documentId: number, title: string) => {
    setDownloadingId(documentId)
    try {
      await downloadAuditReportPdf(documentId, `juriscan-audit-${documentId}.pdf`)
      toast({
        title: "Download started",
        description: `Exported audit report for "${title}".`,
      })
    } catch (err) {
      toast({
        title: "Download failed",
        description: err instanceof Error ? err.message : "Could not generate PDF report.",
        variant: "destructive",
      })
    } finally {
      setDownloadingId(null)
    }
  }

  const resetFilters = () => {
    setSearch("")
    setRiskFilter("ALL")
    setStatusFilter("ALL")
    setDateFrom("")
    setDateTo("")
  }

  const hasActiveFilters = Boolean(
    search.trim() || riskFilter !== "ALL" || statusFilter !== "ALL" || dateFrom || dateTo,
  )

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6">
      {/* Page Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl text-foreground">
            Audit Reports
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Persisted legal compliance audits, detected clause risks, and verified contract histories.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              void fetchOverview()
              void fetchReports()
            }}
            disabled={loadingReports}
            className="border-white/10 hover:border-primary/40"
          >
            <RefreshCw className={`size-3.5 mr-1.5 ${loadingReports ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button asChild size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium">
            <Link to="/dashboard/upload">
              <Upload className="size-3.5 mr-1.5" />
              Upload Contract
            </Link>
          </Button>
        </div>
      </div>

      {/* Engine Notice */}
      <Alert className="border-primary/20 bg-primary/5 py-3 text-xs text-muted-foreground">
        <ShieldCheck className="size-4 text-primary" />
        <AlertTitle className="text-xs font-semibold text-primary">Deterministic Analysis Engine</AlertTitle>
        <AlertDescription className="text-xs">
          Audit reports are derived directly from persisted contract analyses using the rule-based{" "}
          <span className="font-mono text-foreground font-medium">juriscan-rules-v1</span> engine.
          No synthetic metrics or unverified legal assertions are fabricated.
        </AlertDescription>
      </Alert>

      {/* Overview Stat Cards */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard
          label="Total Audited"
          value={overview?.total_reports ?? (loadingOverview ? "—" : 0)}
          icon={FileText}
          hint="Company contracts"
        />
        <StatCard
          label="High Risk"
          value={overview?.high_risk_reports ?? (loadingOverview ? "—" : 0)}
          icon={ShieldAlert}
          tone="destructive"
          hint="Requires review"
        />
        <StatCard
          label="Medium Risk"
          value={overview?.medium_risk_reports ?? (loadingOverview ? "—" : 0)}
          icon={AlertTriangle}
          tone="warning"
          hint="Moderate clauses"
        />
        <StatCard
          label="Low Risk"
          value={overview?.low_risk_reports ?? (loadingOverview ? "—" : 0)}
          icon={CheckCircle2}
          tone="success"
          hint="Routine wording"
        />
        <StatCard
          label="Need Attention"
          value={overview?.requiring_attention ?? (loadingOverview ? "—" : 0)}
          icon={Clock}
          tone={overview && overview.requiring_attention > 0 ? "destructive" : "default"}
          hint="Critical or failed"
        />
        <StatCard
          label="Avg Risk Score"
          value={overview ? `${overview.avg_risk_score}/100` : "—"}
          tone={overview && overview.avg_risk_score >= 50 ? "warning" : "success"}
          hint="Lower is safer"
        />
      </div>

      {/* Filter and Search Bar */}
      <Card className="border-border/60 bg-card/60 backdrop-blur-sm">
        <CardContent className="p-4">
          <div className="grid gap-3 md:grid-cols-12 items-end">
            <div className="md:col-span-4 flex flex-col gap-1.5">
              <Label className="text-xs font-medium text-muted-foreground">Search Documents</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  placeholder="Filter by document title or filename..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9 bg-background/50 text-sm h-9"
                />
              </div>
            </div>

            <div className="md:col-span-2 flex flex-col gap-1.5">
              <Label className="text-xs font-medium text-muted-foreground">Risk Level</Label>
              <Select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
                <option value="ALL">All Risk Levels</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </Select>
            </div>

            <div className="md:col-span-2 flex flex-col gap-1.5">
              <Label className="text-xs font-medium text-muted-foreground">Report Status</Label>
              <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value="ALL">All Statuses</option>
                <option value="COMPLETED">Completed</option>
                <option value="PROCESSING">Processing</option>
                <option value="UPLOADED">Uploaded</option>
                <option value="FAILED">Failed</option>
              </Select>
            </div>

            <div className="md:col-span-3 grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-medium text-muted-foreground">From Date</Label>
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="bg-background/50 text-xs h-9 px-2"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs font-medium text-muted-foreground">To Date</Label>
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="bg-background/50 text-xs h-9 px-2"
                />
              </div>
            </div>

            <div className="md:col-span-1 flex items-end">
              {hasActiveFilters && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={resetFilters}
                  className="h-9 px-2.5 text-xs text-muted-foreground hover:text-foreground w-full"
                  title="Reset filters"
                >
                  <X className="size-3.5 mr-1" />
                  Reset
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Reports Table */}
      <Card className="border-border/60 bg-card/40">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base font-semibold">
            Audit Report History ({reports.length})
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            Scoped to company workspace
          </span>
        </CardHeader>
        <CardContent className="p-0">
          {loadingReports ? (
            <div className="p-6">
              <LoadingSkeleton rows={5} />
            </div>
          ) : reportsError ? (
            <div className="p-6">
              <ErrorState
                title="Could not load audit reports"
                description={reportsError}
                onRetry={() => void fetchReports()}
              />
            </div>
          ) : reports.length === 0 ? (
            <div className="p-8">
              {hasActiveFilters ? (
                <EmptyState
                  icon={Filter}
                  title="No matching reports found"
                  description="Try adjusting or resetting your search filters."
                  action={
                    <Button variant="outline" size="sm" onClick={resetFilters}>
                      Clear Filters
                    </Button>
                  }
                />
              ) : (
                <EmptyState
                  icon={ShieldAlert}
                  title="No audit reports yet"
                  description="Upload your company's contracts to generate automated rule-based compliance audits."
                  action={
                    <Button asChild size="sm">
                      <Link to="/dashboard/upload">
                        <Upload className="size-4 mr-1.5" />
                        Upload First Contract
                      </Link>
                    </Button>
                  }
                />
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/40 hover:bg-transparent">
                    <TableHead className="w-[30%]">Document</TableHead>
                    <TableHead>Audit Date</TableHead>
                    <TableHead>Risk Assessment</TableHead>
                    <TableHead className="hidden md:table-cell">Legal Safety</TableHead>
                    <TableHead>Issues Flagged</TableHead>
                    <TableHead>Report Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reports.map((report) => {
                    const level = toRiskLevel(report.risk_level)
                    const isReady = report.report_status === "READY" || report.report_status === "COMPLETED"
                    const isDownloading = downloadingId === report.document_id

                    return (
                      <TableRow key={report.document_id} className="border-border/30 hover:bg-muted/30">
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 border border-primary/20 text-primary">
                              <FileText className="size-4" />
                            </div>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-foreground">
                                {report.document_title}
                              </p>
                              <div className="flex items-center gap-2 mt-0.5">
                                <Badge variant="outline" className="text-[10px] px-1 py-0 uppercase">
                                  {formatFileType(report.file_type)}
                                </Badge>
                                <span className="truncate text-xs text-muted-foreground">
                                  {report.filename}
                                </span>
                              </div>
                            </div>
                          </div>
                        </TableCell>

                        <TableCell className="text-xs text-muted-foreground">
                          {report.audit_date ? formatDate(report.audit_date) : "—"}
                        </TableCell>

                        <TableCell>
                          {level ? (
                            <div className="flex items-center gap-2">
                              <SeverityBadge level={level} />
                              <span className="text-xs font-mono text-muted-foreground">
                                {Math.round(report.risk_score ?? 0)}/100
                              </span>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>

                        <TableCell className="hidden md:table-cell">
                          {report.safety_score !== null ? (
                            <span className="text-xs font-mono font-medium text-emerald-400">
                              {report.safety_score}/100
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>

                        <TableCell>
                          <div className="text-xs">
                            <span className="font-semibold text-foreground">{report.finding_count}</span>
                            {report.high_risk_count > 0 && (
                              <span className="ml-1 text-red-400 font-medium">
                                ({report.high_risk_count} critical/high)
                              </span>
                            )}
                          </div>
                        </TableCell>

                        <TableCell>
                          {(() => {
                            const status = report.report_status.toUpperCase()
                            if (status === "READY" || status === "COMPLETED") {
                              return (
                                <Badge className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 text-[11px] font-medium flex items-center gap-1 w-fit">
                                  <CheckCircle2 className="size-3" />
                                  Completed
                                </Badge>
                              )
                            }
                            if (status === "FAILED") {
                              return (
                                <Badge variant="destructive" className="text-[11px] font-medium flex items-center gap-1 w-fit">
                                  <AlertTriangle className="size-3" />
                                  Failed
                                </Badge>
                              )
                            }
                            if (status === "PENDING" || status === "PROCESSING") {
                              return (
                                <Badge variant="secondary" className="bg-amber-500/15 text-amber-300 border border-amber-500/30 text-[11px] font-medium flex items-center gap-1 w-fit">
                                  <Clock className="size-3 animate-spin" />
                                  Processing
                                </Badge>
                              )
                            }
                            return (
                              <Badge variant="outline" className="text-muted-foreground border-white/10 text-[11px] font-medium flex items-center gap-1 w-fit">
                                <FileText className="size-3" />
                                Uploaded
                              </Badge>
                            )
                          })()}
                        </TableCell>

                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {report.report_status === "FAILED" && (
                              <Button
                                asChild
                                variant="outline"
                                size="sm"
                                className="h-8 text-xs px-2.5 border-destructive/40 text-destructive hover:bg-destructive/10"
                                title="Re-upload or re-analyze this contract"
                              >
                                <Link to="/dashboard/upload">
                                  <RotateCcw className="size-3.5 mr-1" />
                                  Retry
                                </Link>
                              </Button>
                            )}
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void openReportDetail(report.document_id)}
                              className="h-8 text-xs px-2.5 border-white/10 hover:border-primary/40 hover:text-primary"
                            >
                              <Eye className="size-3.5 mr-1" />
                              Details
                            </Button>
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => void handleDownloadPdf(report.document_id, report.document_title)}
                              disabled={!isReady || isDownloading}
                              className="h-8 text-xs px-2.5"
                              title={isReady ? "Download PDF Audit Report" : "Report not ready yet"}
                            >
                              {isDownloading ? (
                                <Spinner className="size-3.5 mr-1" />
                              ) : (
                                <Download className="size-3.5 mr-1" />
                              )}
                              PDF
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

      {/* Report Detail Modal */}
      <Dialog open={selectedReportId !== null} onOpenChange={(open) => !open && setSelectedReportId(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-card border-border/80">
          <DialogHeader>
            <div className="flex items-start justify-between gap-4">
              <div>
                <DialogTitle className="text-lg font-semibold text-foreground">
                  {detailData?.document_title ?? "Contract Audit Report"}
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground mt-1">
                  Filename: {detailData?.filename} • Analyzed{" "}
                  {detailData?.audit_date ? formatDate(detailData.audit_date) : "—"}
                </DialogDescription>
              </div>
              <Badge variant="outline" className="text-xs border-primary/30 text-primary shrink-0">
                {detailData?.model_name || "juriscan-rules-v1"}
              </Badge>
            </div>
          </DialogHeader>

          {loadingDetail ? (
            <div className="py-12">
              <LoadingSkeleton rows={6} />
            </div>
          ) : detailError ? (
            <ErrorState
              title="Could not load report details"
              description={detailError}
              onRetry={() => selectedReportId && void openReportDetail(selectedReportId)}
            />
          ) : detailData ? (
            <div className="flex flex-col gap-5 py-2">
              {detailData.error_message && (
                <Alert variant="destructive" className="py-2.5">
                  <AlertTriangle className="size-4" />
                  <AlertTitle className="text-xs font-semibold">Analysis Failed</AlertTitle>
                  <AlertDescription className="text-xs">
                    {detailData.error_message}
                    <div className="mt-2">
                      <Button asChild size="sm" variant="outline" className="h-7 text-xs border-destructive/40 text-destructive hover:bg-destructive/10">
                        <Link to="/dashboard/upload">
                          <RotateCcw className="size-3 mr-1" />
                          Retry Upload in Workspace
                        </Link>
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              )}
              {/* Summary Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 rounded-lg border border-border/60 bg-muted/20 p-3">
                <div>
                  <p className="text-[11px] font-medium text-muted-foreground uppercase">Risk Score</p>
                  <p className="text-lg font-bold text-foreground">
                    {Math.round(detailData.risk_score ?? 0)}/100
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-medium text-muted-foreground uppercase">Safety Score</p>
                  <p className="text-lg font-bold text-emerald-400">
                    {detailData.safety_score ?? "—"}/100
                  </p>
                </div>
                <div>
                  <p className="text-[11px] font-medium text-muted-foreground uppercase">Clauses Checked</p>
                  <p className="text-lg font-bold text-foreground">{detailData.clause_count}</p>
                </div>
                <div>
                  <p className="text-[11px] font-medium text-muted-foreground uppercase">Issues Flagged</p>
                  <p className="text-lg font-bold text-foreground">{detailData.finding_count}</p>
                </div>
              </div>

              {/* Assessment Narrative */}
              {detailData.analysis_summary && (
                <div className="rounded-lg border border-border/50 bg-background/40 p-3.5">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                    Executive Summary
                  </h4>
                  <p className="text-sm leading-relaxed text-foreground/90">
                    {detailData.analysis_summary}
                  </p>
                </div>
              )}

              {/* Engine Transparency Notice */}
              <div className="text-[11px] text-muted-foreground/80 rounded-md border border-white/5 bg-background/30 p-2.5">
                <span className="font-semibold text-foreground/90">Explainable Baseline:</span> This audit was
                conducted using deterministic pattern-matching rules for contract risks (arbitration clauses,
                unilateral termination, indemnification liabilities, confidentiality overbreadth). No
                unverified machine learning output is presented.
              </div>

              {/* Identified Issues */}
              <div className="flex flex-col gap-3">
                <h4 className="text-sm font-semibold text-foreground flex items-center justify-between">
                  <span>Detected Issues & Clauses ({detailData.findings.length})</span>
                  <span className="text-xs text-muted-foreground font-normal">
                    Sorted by severity
                  </span>
                </h4>

                {detailData.findings.length === 0 ? (
                  <div className="text-center py-6 border border-dashed border-border/60 rounded-lg text-muted-foreground text-sm">
                    No risk indicators were flagged for this contract.
                  </div>
                ) : (
                  detailData.findings.map((finding) => (
                    <div
                      key={finding.id}
                      className="rounded-lg border border-border/60 bg-card/60 p-4 flex flex-col gap-2.5"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <SeverityBadge level={toRiskLevel(finding.severity) ?? "low"} />
                          <h5 className="text-sm font-medium text-foreground">{finding.title}</h5>
                        </div>
                        {finding.clause_number !== null && (
                          <span className="text-xs font-mono text-muted-foreground">
                            Clause {finding.clause_number}
                            {finding.clause_page ? ` (p. ${finding.clause_page})` : ""}
                          </span>
                        )}
                      </div>

                      {finding.clause_heading && (
                        <p className="text-xs font-medium text-primary/90">
                          Section: {finding.clause_heading}
                        </p>
                      )}

                      <p className="text-xs text-muted-foreground leading-relaxed">
                        <strong className="text-foreground">Why it was flagged:</strong> {finding.description}
                      </p>

                      {finding.citation && (
                        <div className="rounded bg-background/50 border border-border/40 px-2.5 py-1.5 text-xs">
                          <span className="font-semibold text-amber-400/90 mr-1.5">Legal Reference:</span>
                          <span className="text-foreground/80">{finding.citation}</span>
                        </div>
                      )}

                      {finding.recommendation && (
                        <div className="rounded bg-primary/5 border border-primary/20 px-2.5 py-1.5 text-xs">
                          <span className="font-semibold text-primary mr-1.5">Suggested Action:</span>
                          <span className="text-foreground/90">{finding.recommendation}</span>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}

          <DialogFooter className="mt-4 flex sm:justify-between items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedReportId(null)}
            >
              Close
            </Button>
            {detailData && (detailData.report_status === "READY" || detailData.report_status === "COMPLETED") && (
              <Button
                size="sm"
                onClick={() => void handleDownloadPdf(detailData.document_id, detailData.document_title)}
                disabled={downloadingId === detailData.document_id}
                className="bg-primary text-primary-foreground hover:bg-primary/90"
              >
                {downloadingId === detailData.document_id ? (
                  <Spinner className="size-3.5 mr-1.5" />
                ) : (
                  <Download className="size-3.5 mr-1.5" />
                )}
                Download Full PDF Report
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
export default AuditReportsPage
