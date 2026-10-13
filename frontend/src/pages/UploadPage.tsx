import {
  AlertTriangle,
  CheckCircle2,
  CloudUpload,
  ExternalLink,
  FileText,
  Loader2,
  RotateCcw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { Link } from "react-router-dom"

import { AnalysisResults } from "@/components/analysis/AnalysisResults"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { useToast } from "@/components/ui/toast"
import { ApiError } from "@/lib/api"
import { uploadDocument } from "@/lib/documents"
import type { DocumentDetail, DuplicateDocumentDetails } from "@/lib/types"
import { cn } from "@/lib/utils"

const ACCEPTED = [".pdf", ".docx", ".txt"]
const MAX_SIZE = 25 * 1024 * 1024

const pipelineStages = [
  "Validate file type and size",
  "Extract text (PDF / DOCX / TXT)",
  "Segment clauses with offsets",
  "Run explainable rule-based analysis",
  "Store document, clauses, analysis and findings",
]

interface SelectedFile {
  id: string
  file: File
}

interface InvalidFile {
  id: string
  name: string
  reason: string
}

type ResultStatus = "ok" | "duplicate" | "error"

interface UploadResult {
  id: string
  filename: string
  status: ResultStatus
  message: string
  document?: DocumentDetail
  documentId?: number
  analysisId?: number
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function UploadPage() {
  const [files, setFiles] = useState<SelectedFile[]>([])
  const [invalidFiles, setInvalidFiles] = useState<InvalidFile[]>([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [fileProgress, setFileProgress] = useState<Record<string, number>>({})
  const [completed, setCompleted] = useState(0)
  const [results, setResults] = useState<UploadResult[]>([])
  const [reanalyzingId, setReanalyzingId] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  const lastSuccess = useMemo(
    () => [...results].reverse().find((result) => result.status === "ok")?.document,
    [results],
  )

  const issueResults = useMemo(
    () => results.filter((result) => result.status !== "ok"),
    [results],
  )

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return
    const next: SelectedFile[] = []
    const rejected: InvalidFile[] = []
    for (const file of Array.from(incoming)) {
      const lower = file.name.toLowerCase()
      const id = `${file.name}-${file.size}-${Math.random().toString(36).slice(2)}`
      if (!ACCEPTED.some((ext) => lower.endsWith(ext))) {
        rejected.push({
          id,
          name: file.name,
          reason: "Unsupported file type — only PDF, DOCX and TXT are accepted.",
        })
        continue
      }
      if (file.size === 0) {
        rejected.push({ id, name: file.name, reason: "The file is empty (0 bytes)." })
        continue
      }
      if (file.size > MAX_SIZE) {
        rejected.push({
          id,
          name: file.name,
          reason: `The file is ${formatSize(file.size)}, exceeding the 25 MB limit.`,
        })
        continue
      }
      next.push({ id, file })
    }
    if (next.length > 0) setFiles((current) => [...current, ...next])
    if (rejected.length > 0) {
      setInvalidFiles((current) => [...current, ...rejected])
      toast({
        title: "Some files were rejected",
        description: `${rejected.length} file(s) failed client-side validation.`,
        variant: "destructive",
      })
    }
  }

  const removeFile = (id: string) => {
    setFiles((current) => current.filter((item) => item.id !== id))
    setFileProgress((current) => {
      const next = { ...current }
      delete next[id]
      return next
    })
  }

  const removeInvalid = (id: string) =>
    setInvalidFiles((current) => current.filter((item) => item.id !== id))

  const clearAll = () => {
    setFiles([])
    setInvalidFiles([])
    setFileProgress({})
  }

  const resetAll = () => {
    setFiles([])
    setInvalidFiles([])
    setFileProgress({})
    setResults([])
    setCompleted(0)
  }

  const analyze = async () => {
    if (files.length === 0 || uploading) return
    setUploading(true)
    setCompleted(0)
    setResults([])
    setFileProgress({})

    const collected: UploadResult[] = []
    for (const item of files) {
      setActiveId(item.id)
      setFileProgress((current) => ({ ...current, [item.id]: 0 }))
      try {
        const document = await uploadDocument(item.file, undefined, (percent) => {
          setFileProgress((current) => ({ ...current, [item.id]: percent }))
        })
        collected.push({
          id: item.id,
          filename: item.file.name,
          status: "ok",
          message: `Analyzed — legal safety ${Math.round(document.safety_score ?? 0)}/100, risk ${(document.risk_level ?? "—").toLowerCase()}, ${document.finding_count} finding(s).`,
          document,
        })
      } catch (error) {
        if (error instanceof ApiError && error.code === "duplicate_document") {
          const details = (error.details ?? {}) as DuplicateDocumentDetails
          const alreadyAnalyzed = details.analysis_id != null
          collected.push({
            id: item.id,
            filename: item.file.name,
            status: "duplicate",
            message:
              details.status === "PROCESSING"
                ? "This file is already being processed. Wait a moment, then open the analysis."
                : alreadyAnalyzed
                  ? "Already analyzed. Open the existing analysis, or analyze it again to refresh the findings."
                  : "Already uploaded but not analyzed yet. Use \u201cAnalyze again\u201d to run the analysis.",
            documentId: details.document_id,
            analysisId: details.analysis_id ?? undefined,
          })
        } else {
          collected.push({
            id: item.id,
            filename: item.file.name,
            status: "error",
            message: error instanceof ApiError ? error.message : "Upload failed.",
          })
        }
      }
      setCompleted((count) => count + 1)
      setResults([...collected])
    }

    setActiveId(null)
    setUploading(false)
    const succeeded = collected.filter((result) => result.status === "ok").length
    const duplicates = collected.filter((result) => result.status === "duplicate").length
    const errors = collected.filter((result) => result.status === "error").length
    if (succeeded > 0 && duplicates === 0 && errors === 0) {
      toast({
        title: "Analysis complete",
        description: `${succeeded} document(s) analyzed with the rule-based baseline.`,
        variant: "success",
      })
    } else if (succeeded > 0) {
      toast({
        title: "Partially completed",
        description: `${succeeded} analyzed, ${duplicates} already analyzed, ${errors} failed.`,
        variant: "warning",
      })
    } else if (duplicates > 0 && errors === 0) {
      toast({
        title: "Already analyzed",
        description: `${duplicates} file(s) were already analyzed. Open the existing analysis or choose \u201cAnalyze again\u201d.`,
        variant: "warning",
      })
    } else {
      const reasons: string[] = []
      if (duplicates > 0) reasons.push(`${duplicates} already analyzed`)
      if (errors > 0) reasons.push(`${errors} failed`)
      toast({
        title: errors > 0 ? "Nothing analyzed" : "Already analyzed",
        description: reasons.length
          ? `${reasons.join(", ")}. See the per-file details below.`
          : "No documents could be processed. See the per-file details below.",
        variant: errors > 0 ? "destructive" : "warning",
      })
    }
  }

  const analyzeAgain = async (result: UploadResult) => {
    const item = files.find((entry) => entry.id === result.id)
    if (!item || reanalyzingId !== null || uploading) return
    setReanalyzingId(result.id)
    setFileProgress((current) => ({ ...current, [result.id]: 0 }))
    try {
      const document = await uploadDocument(
        item.file,
        undefined,
        (percent) => {
          setFileProgress((current) => ({ ...current, [result.id]: percent }))
        },
        true,
      )
      setResults((current) =>
        current.map((entry) =>
          entry.id === result.id
            ? {
                id: entry.id,
                filename: entry.filename,
                status: "ok" as const,
                message: `Analyzed — legal safety ${Math.round(document.safety_score ?? 0)}/100, risk ${(document.risk_level ?? "—").toLowerCase()}, ${document.finding_count} finding(s).`,
                document,
              }
            : entry,
        ),
      )
      toast({
        title: "Re-analysis complete",
        description: `${item.file.name} was analyzed again.`,
        variant: "success",
      })
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Upload failed."
      setResults((current) =>
        current.map((entry) =>
          entry.id === result.id ? { ...entry, status: "error" as const, message } : entry,
        ),
      )
      toast({ title: "Re-analysis failed", description: message, variant: "destructive" })
    } finally {
      setReanalyzingId(null)
      setFileProgress((current) => {
        const next = { ...current }
        delete next[result.id]
        return next
      })
    }
  }

  const renderIssueActions = (result: UploadResult) => {
    if (result.status !== "duplicate" || result.documentId === undefined) return null
    const busy = reanalyzingId === result.id
    return (
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {result.analysisId !== undefined ? (
          <Button asChild variant="outline" size="sm">
            <Link to={`/dashboard/analyses/${result.documentId}`}>
              <ExternalLink className="size-4" aria-hidden="true" />
              View existing analysis
            </Link>
          </Button>
        ) : null}
        <Button
          variant="secondary"
          size="sm"
          disabled={busy || uploading}
          onClick={() => void analyzeAgain(result)}
        >
          {busy ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <RotateCcw className="size-4" aria-hidden="true" />
          )}
          Analyze again
        </Button>
      </div>
    )
  }

  const overallProgress = files.length === 0 ? 0 : (completed / files.length) * 100
  const hasResults = results.length > 0
  const hasInvalid = invalidFiles.length > 0
  const showResults = lastSuccess !== undefined && !uploading

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Contract Risk Analysis</h1>
        <p className="text-sm text-muted-foreground">
          Upload a contract to identify potential contractual risks and get a plain-English
          review on this page.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-muted/40 px-3 py-2.5 text-xs text-muted-foreground">
        Files are uploaded to the JurisScan-AI backend and analyzed with an{" "}
        <span className="font-medium text-foreground">explainable rule-based baseline</span>. No
        machine-learning model (including Legal-BERT) is trained or used.
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="flex min-w-0 flex-col gap-4">
          {showResults ? (
            <>
              {issueResults.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Other files</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {issueResults.map((result) => (
                      <div
                        key={result.id}
                        className="flex items-start gap-3 rounded-lg border border-border px-3 py-2.5"
                      >
                        {result.status === "duplicate" ? (
                          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden="true" />
                        ) : (
                          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{result.filename}</p>
                          <p className="text-xs text-muted-foreground">{result.message}</p>
                          {renderIssueActions(result)}
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}
              {lastSuccess ? <AnalysisResults doc={lastSuccess} onAnalyzeAnother={resetAll} /> : null}
            </>
          ) : (
            <>
              <Card>
                <CardContent>
                  <label
                    onDragOver={(event) => {
                      event.preventDefault()
                      setDragging(true)
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(event) => {
                      event.preventDefault()
                      setDragging(false)
                      addFiles(event.dataTransfer.files)
                    }}
                    className={cn(
                      "flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
                      dragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/40",
                      uploading && "pointer-events-none opacity-60",
                    )}
                  >
                    <span className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <CloudUpload className="size-6" aria-hidden="true" />
                    </span>
                    <div>
                      <p className="font-medium">Drag &amp; drop your contract here</p>
                      <p className="text-sm text-muted-foreground">or click to browse your files</p>
                    </div>
                    <input
                      ref={inputRef}
                      type="file"
                      multiple
                      accept={ACCEPTED.join(",")}
                      className="sr-only"
                      onChange={(event) => {
                        addFiles(event.target.files)
                        event.target.value = ""
                      }}
                    />
                    <span className="text-xs text-muted-foreground">PDF · DOCX · TXT — up to 25 MB each</span>
                  </label>
                </CardContent>
              </Card>

              {files.length > 0 ? (
                <Card>
                  <CardHeader className="flex-row items-center justify-between">
                    <CardTitle>Selected files ({files.length})</CardTitle>
                    <Button variant="ghost" size="sm" onClick={clearAll} disabled={uploading}>
                      Clear all
                    </Button>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {files.map((item) => {
                      const percent = fileProgress[item.id]
                      const result = results.find((entry) => entry.id === item.id)
                      const isActive = uploading && activeId === item.id && result === undefined
                      return (
                        <div
                          key={item.id}
                          className="flex flex-col gap-2 rounded-lg border border-border px-3 py-2.5"
                        >
                          <div className="flex items-center gap-3">
                            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
                              <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium">{item.file.name}</p>
                              <p className="text-xs text-muted-foreground">
                                {formatSize(item.file.size)}
                                {isActive && percent !== undefined ? ` · uploading ${percent}%` : ""}
                                {result?.status === "ok" ? " · analyzed" : ""}
                                {result?.status === "duplicate" ? " · duplicate" : ""}
                                {result?.status === "error" ? " · failed" : ""}
                              </p>
                            </div>
                            {isActive ? (
                              <Loader2 className="size-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
                            ) : result?.status === "ok" ? (
                              <CheckCircle2 className="size-4 shrink-0 text-emerald-500" aria-hidden="true" />
                            ) : result ? (
                              <AlertTriangle className="size-4 shrink-0 text-amber-500" aria-hidden="true" />
                            ) : (
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Remove ${item.file.name}`}
                                onClick={() => removeFile(item.id)}
                                disabled={uploading}
                              >
                                <Trash2 className="size-4" aria-hidden="true" />
                              </Button>
                            )}
                          </div>
                          {isActive ? <Progress value={percent ?? 0} /> : null}
                        </div>
                      )
                    })}
                  </CardContent>
                </Card>
              ) : null}

              {hasInvalid ? (
                <Card>
                  <CardHeader className="flex-row items-center justify-between">
                    <CardTitle>Rejected files ({invalidFiles.length})</CardTitle>
                    <Button variant="ghost" size="sm" onClick={() => setInvalidFiles([])}>
                      Dismiss
                    </Button>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {invalidFiles.map((item) => (
                      <div
                        key={item.id}
                        className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2.5"
                      >
                        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{item.name}</p>
                          <p className="text-xs text-muted-foreground">{item.reason}</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Dismiss ${item.name}`}
                          onClick={() => removeInvalid(item.id)}
                        >
                          <X className="size-4" aria-hidden="true" />
                        </Button>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}

              {hasResults ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Results</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {results.map((result) => (
                      <div key={result.id} className="flex items-start gap-3 rounded-lg border border-border px-3 py-2.5">
                        {result.status === "ok" ? (
                          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-500" aria-hidden="true" />
                        ) : result.status === "duplicate" ? (
                          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden="true" />
                        ) : (
                          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{result.filename}</p>
                          <p className="text-xs text-muted-foreground">{result.message}</p>
                          {renderIssueActions(result)}
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}
            </>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Analysis pipeline</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <ol className="flex flex-col gap-3">
                {pipelineStages.map((stage, index) => (
                  <li key={stage} className="flex items-center gap-3 text-sm">
                    <span
                      className={cn(
                        "flex size-6 items-center justify-center rounded-full border text-xs",
                        uploadProgressState(index, completed, files.length, uploading) === "done" &&
                          "border-emerald-500 bg-emerald-500 text-white",
                        uploadProgressState(index, completed, files.length, uploading) === "active" &&
                          "border-primary text-primary",
                        uploadProgressState(index, completed, files.length, uploading) === "idle" &&
                          "border-border text-muted-foreground",
                      )}
                    >
                      {uploadProgressState(index, completed, files.length, uploading) === "done" ? (
                        <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      ) : uploadProgressState(index, completed, files.length, uploading) === "active" ? (
                        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                      ) : (
                        index + 1
                      )}
                    </span>
                    <span className="text-muted-foreground">{stage}</span>
                  </li>
                ))}
              </ol>

              {uploading ? (
                <div className="flex flex-col gap-2">
                  <Progress value={overallProgress} />
                  <p className="text-xs text-muted-foreground">
                    {completed} of {files.length} processed
                  </p>
                </div>
              ) : null}

              {!showResults ? (
                <div className="flex flex-col gap-2 border-t border-border pt-4">
                  <Button onClick={() => void analyze()} disabled={files.length === 0 || uploading}>
                    {uploading ? (
                      <>
                        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                        Analyzing…
                      </>
                    ) : (
                      <>
                        <Sparkles className="size-4" aria-hidden="true" />
                        Upload &amp; analyze
                      </>
                    )}
                  </Button>
                  {hasResults && !uploading ? (
                    <Button variant="ghost" size="sm" onClick={() => setResults([])}>
                      <X className="size-4" aria-hidden="true" />
                      Clear results
                    </Button>
                  ) : null}
                </div>
              ) : (
                <div className="flex flex-col gap-2 border-t border-border pt-4">
                  <Button variant="outline" onClick={resetAll}>
                    <FileText aria-hidden="true" />
                    Analyze another document
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Accepted formats</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Badge variant="secondary">PDF</Badge>
              <Badge variant="secondary">DOCX</Badge>
              <Badge variant="secondary">TXT</Badge>
              <Badge variant="outline">≤ 25 MB</Badge>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function uploadProgressState(
  index: number,
  completed: number,
  total: number,
  uploading: boolean,
): "idle" | "active" | "done" {
  if (!uploading && completed === 0) return "idle"
  if (!uploading && completed >= total && total > 0) return "done"
  const fraction = total === 0 ? 0 : completed / total
  const stageIndex = Math.min(pipelineStages.length - 1, Math.floor(fraction * pipelineStages.length))
  if (index < stageIndex) return "done"
  if (index === stageIndex) return "active"
  return "idle"
}