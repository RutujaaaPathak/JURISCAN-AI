import { CheckCircle2, FileText, Info, Paperclip } from "lucide-react"
import { useCallback, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useRole } from "@/context/RoleContext"
import { useAsync } from "@/hooks/useAsync"
import { ApiError } from "@/lib/api"
import { createCase } from "@/lib/cases"
import {
  CASE_CATEGORY_VALUES,
  CASE_URGENCY_OPTIONS,
  caseCategoryLabel,
  urgencyLabel,
} from "@/lib/caseFilters"
import { listDocuments } from "@/lib/documents"
import { formatFileType } from "@/lib/format"
import type { CaseDetail } from "@/lib/types"

const CATEGORY_OPTIONS = CASE_CATEGORY_VALUES.map((value) => ({
  value,
  label: caseCategoryLabel(value),
}))

const CONSULTATION_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "video", label: "Video call" },
  { value: "phone", label: "Phone" },
  { value: "in-person", label: "In person" },
  { value: "chat", label: "Chat" },
]

const STEPS = ["Basics", "Details", "Documents", "Review"] as const

interface FormState {
  title: string
  category: string
  urgency: string
  summary: string
  jurisdiction: string
  deadline: string
  budget: string
  consultation_method: string
  contact_preference: string
}

const EMPTY_FORM: FormState = {
  title: "",
  category: "property",
  urgency: "MEDIUM",
  summary: "",
  jurisdiction: "",
  deadline: "",
  budget: "",
  consultation_method: "",
  contact_preference: "",
}

function validateBasics(form: FormState): string | null {
  if (form.title.trim().length < 3) return "Give your case a title of at least 3 characters."
  if (!form.category) return "Choose a legal category."
  return null
}

function validateDetails(form: FormState): string | null {
  if (form.summary.trim().length < 10) {
    return "Describe the matter in at least 10 characters so lawyers can assess it."
  }
  return null
}

export function PostCasePage() {
  const { role } = useRole()
  const [searchParams] = useSearchParams()
  const requestedLawyer = searchParams.get("lawyer")

  const [form, setForm] = useState<FormState>(() => ({
    ...EMPTY_FORM,
    category: searchParams.get("category") ?? EMPTY_FORM.category,
  }))
  const [step, setStep] = useState(0)
  const [selectedDocs, setSelectedDocs] = useState<number[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<CaseDetail | null>(null)

  const docsLoader = useCallback(() => listDocuments({ limit: 50 }), [])
  const { state: docsState, refresh: refreshDocs } = useAsync(docsLoader)

  function update<K extends keyof FormState>(key: K, value: string) {
    setForm((previous) => ({ ...previous, [key]: value }))
  }

  function toggleDoc(id: number) {
    setSelectedDocs((previous) =>
      previous.includes(id) ? previous.filter((value) => value !== id) : [...previous, id],
    )
  }

  function next() {
    const problem = step === 0 ? validateBasics(form) : step === 1 ? validateDetails(form) : null
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setStep((current) => Math.min(current + 1, STEPS.length - 1))
  }

  async function submit() {
    const problem = validateBasics(form) ?? validateDetails(form)
    if (problem) {
      setError(problem)
      return
    }
    setBusy(true)
    setError(null)
    try {
      const deadline = form.deadline ? new Date(form.deadline).toISOString() : null
      const created = await createCase({
        title: form.title.trim(),
        category: form.category,
        summary: form.summary.trim(),
        urgency: form.urgency,
        jurisdiction: form.jurisdiction.trim() || null,
        deadline,
        budget: form.budget.trim() || null,
        consultation_method: form.consultation_method || null,
        contact_preference: form.contact_preference.trim() || null,
        document_ids: selectedDocs,
      })
      setCreated(created)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Your case could not be submitted.")
    } finally {
      setBusy(false)
    }
  }

  if (created) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <span className="flex size-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
              <CheckCircle2 className="size-6" aria-hidden="true" />
            </span>
            <h1 className="text-xl font-semibold">Case submitted</h1>
            <p className="max-w-md text-sm text-muted-foreground">
              “{created.title}” is now open and visible to eligible lawyers. You will see it under
              My Legal Cases, where lawyer responses and the assigned lawyer will appear.
            </p>
            <Badge variant="outline">Status: {created.status === "OPEN" ? "Open" : created.status}</Badge>
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              <Button asChild>
                <Link to={`/dashboard/cases/${created.id}`}>View case</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link to="/dashboard/legal-cases">My legal cases</Link>
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setCreated(null)
                  setForm({ ...EMPTY_FORM })
                  setSelectedDocs([])
                  setStep(0)
                }}
              >
                Post another case
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const documents = docsState.data?.items ?? []

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Post a case</h1>
        <p className="text-sm text-muted-foreground">
          Describe your legal matter so eligible lawyers can review it and respond.
        </p>
      </div>

      {role !== "individual" && role !== "company" ? (
        <div className="rounded-lg border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
          Note: you are previewing as “{role}”. Cases are posted to your own workspace account.
        </div>
      ) : null}

      {requestedLawyer ? (
        <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <p>
            You came from a lawyer profile. Cases are posted to the shared marketplace, so any
            eligible lawyer may respond — direct invites are not supported yet.
          </p>
        </div>
      ) : null}

      <ol className="flex flex-wrap gap-2 text-xs">
        {STEPS.map((label, index) => (
          <li key={label} className="flex items-center gap-2">
            <span
              className={
                index <= step
                  ? "flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground"
                  : "flex size-5 items-center justify-center rounded-full bg-muted text-muted-foreground"
              }
            >
              {index + 1}
            </span>
            <span className={index <= step ? "font-medium" : "text-muted-foreground"}>{label}</span>
            {index < STEPS.length - 1 ? <span className="text-muted-foreground">·</span> : null}
          </li>
        ))}
      </ol>

      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{STEPS[step]}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {step === 0 ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="case-title">Case title</Label>
                <Input
                  id="case-title"
                  placeholder="e.g. Boundary dispute with neighbour"
                  value={form.title}
                  onChange={(event) => update("title", event.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="case-category">Legal category</Label>
                  <Select
                    id="case-category"
                    value={form.category}
                    onChange={(event) => update("category", event.target.value)}
                  >
                    {CATEGORY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="case-urgency">Urgency</Label>
                  <Select
                    id="case-urgency"
                    value={form.urgency}
                    onChange={(event) => update("urgency", event.target.value)}
                  >
                    {CASE_URGENCY_OPTIONS.filter((option) => option.value !== "ALL").map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            </>
          ) : null}

          {step === 1 ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="case-summary">Description and relevant facts</Label>
                <Textarea
                  id="case-summary"
                  rows={6}
                  placeholder="What happened, who is involved, and what outcome you are looking for."
                  value={form.summary}
                  onChange={(event) => update("summary", event.target.value)}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="case-jurisdiction">Jurisdiction / location</Label>
                  <Input
                    id="case-jurisdiction"
                    placeholder="e.g. Maharashtra, India"
                    value={form.jurisdiction}
                    onChange={(event) => update("jurisdiction", event.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="case-deadline">Important date / deadline</Label>
                  <Input
                    id="case-deadline"
                    type="datetime-local"
                    value={form.deadline}
                    onChange={(event) => update("deadline", event.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="case-budget">Expected budget or fee preference</Label>
                  <Input
                    id="case-budget"
                    placeholder="e.g. 15,000 fixed, open to hourly"
                    value={form.budget}
                    onChange={(event) => update("budget", event.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="case-consultation">Preferred consultation method</Label>
                  <Select
                    id="case-consultation"
                    value={form.consultation_method}
                    onChange={(event) => update("consultation_method", event.target.value)}
                  >
                    {CONSULTATION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                  <Label htmlFor="case-contact">Availability / contact preference</Label>
                  <Input
                    id="case-contact"
                    placeholder="e.g. Weekday mornings, email preferred"
                    value={form.contact_preference}
                    onChange={(event) => update("contact_preference", event.target.value)}
                  />
                </div>
              </div>
            </>
          ) : null}

          {step === 2 ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Optionally attach documents you have already uploaded. They become visible only to a
                lawyer who accepts your case.
              </p>
              {docsState.phase === "loading" || docsState.phase === "idle" ? (
                <LoadingSkeleton rows={3} />
              ) : docsState.phase === "error" ? (
                <ErrorState
                  title="Could not load your documents"
                  description={docsState.error ?? undefined}
                  onRetry={() => void refreshDocs()}
                />
              ) : documents.length === 0 ? (
                <EmptyState
                  icon={FileText}
                  title="No documents yet"
                  description="You can post the case now and share documents later from the case page."
                  action={
                    <Button asChild size="sm" variant="outline">
                      <Link to="/dashboard/upload">Upload a document</Link>
                    </Button>
                  }
                />
              ) : (
                <ul className="flex flex-col gap-2">
                  {documents.map((doc) => (
                    <li key={doc.id}>
                      <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-border p-3">
                        <input
                          type="checkbox"
                          className="size-4 accent-primary"
                          checked={selectedDocs.includes(doc.id)}
                          onChange={() => toggleDoc(doc.id)}
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">{doc.title}</span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {doc.filename}
                          </span>
                        </span>
                        <Badge variant="outline">{formatFileType(doc.file_type)}</Badge>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}

          {step === 3 ? (
            <div className="flex flex-col gap-3 text-sm">
              <ReviewRow label="Title" value={form.title} />
              <ReviewRow label="Category" value={caseCategoryLabel(form.category)} />
              <ReviewRow label="Urgency" value={urgencyLabel(form.urgency)} />
              <ReviewRow label="Description" value={form.summary} multiline />
              <ReviewRow label="Jurisdiction" value={form.jurisdiction || "—"} />
              <ReviewRow
                label="Deadline"
                value={form.deadline ? new Date(form.deadline).toLocaleString() : "—"}
              />
              <ReviewRow label="Budget" value={form.budget || "—"} />
              <ReviewRow
                label="Consultation"
                value={form.consultation_method || "No preference"}
              />
              <ReviewRow label="Availability" value={form.contact_preference || "—"} />
              <ReviewRow
                label="Documents"
                value={selectedDocs.length > 0 ? `${selectedDocs.length} attached` : "None"}
              />
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          disabled={step === 0 || busy}
          onClick={() => {
            setError(null)
            setStep((current) => Math.max(0, current - 1))
          }}
        >
          Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={next}>Continue</Button>
        ) : (
          <Button disabled={busy} onClick={() => void submit()}>
            <Paperclip className="size-4" aria-hidden="true" />
            Submit case
          </Button>
        )}
      </div>
    </div>
  )
}

function ReviewRow({
  label,
  value,
  multiline,
}: {
  label: string
  value: string
  multiline?: boolean
}) {
  return (
    <div className="grid grid-cols-3 gap-2 border-b border-border pb-2 last:border-b-0">
      <span className="text-muted-foreground">{label}</span>
      <span className={multiline ? "col-span-2 whitespace-pre-line" : "col-span-2"}>{value}</span>
    </div>
  )
}
