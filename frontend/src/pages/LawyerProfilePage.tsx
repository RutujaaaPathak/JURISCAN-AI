import { Info, Save, ShieldCheck } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useAsync } from "@/hooks/useAsync"
import { ApiError } from "@/lib/api"
import { getLawyerProfile, submitLawyerVerification, updateLawyerProfile } from "@/lib/cases"
import type { LawyerProfile } from "@/lib/types"

const VERIFICATION_META: Record<string, { label: string; variant: "outline" | "warning" | "success" | "destructive" }> = {
  UNVERIFIED: { label: "Unverified", variant: "outline" },
  PENDING: { label: "Pending review", variant: "warning" },
  VERIFIED: { label: "Verified", variant: "success" },
  REJECTED: { label: "Rejected", variant: "destructive" },
}

interface FormState {
  full_name: string
  bar_registration_number: string
  jurisdiction: string
  years_experience: string
  practice_areas: string
  languages: string
  location: string
  bio: string
  consultation_modes: string
  fee_structure: string
  availability: string
}

function toForm(profile: LawyerProfile): FormState {
  return {
    full_name: profile.full_name ?? "",
    bar_registration_number: profile.bar_registration_number ?? "",
    jurisdiction: profile.jurisdiction ?? "",
    years_experience: profile.years_experience !== null ? String(profile.years_experience) : "",
    practice_areas: profile.practice_areas.join(", "),
    languages: profile.languages.join(", "),
    location: profile.location ?? "",
    bio: profile.bio ?? "",
    consultation_modes: profile.consultation_modes.join(", "),
    fee_structure: profile.fee_structure ?? "",
    availability: profile.availability ?? "",
  }
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)
}

export function LawyerProfilePage() {
  const loader = useCallback(() => getLawyerProfile(), [])
  const { state, refresh } = useAsync(loader)

  const [form, setForm] = useState<FormState | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (state.data) {
      setForm(toForm(state.data))
    }
  }, [state.data])

  if (state.phase === "loading" || state.phase === "idle") {
    return (
      <div className="mx-auto w-full max-w-4xl">
        <LoadingSkeleton rows={6} />
      </div>
    )
  }

  if (state.phase === "error" || !state.data || !form) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <ErrorState
          title="Could not load your profile"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      </div>
    )
  }

  const profile = state.data
  const status = VERIFICATION_META[profile.verification_status] ?? VERIFICATION_META.UNVERIFIED

  function update<K extends keyof FormState>(key: K, value: string) {
    setForm((previous) => (previous ? { ...previous, [key]: value } : previous))
  }

  async function save() {
    if (!form) return
    setBusy(true)
    setError(null)
    setFeedback(null)
    try {
      const years = form.years_experience.trim()
      await updateLawyerProfile({
        full_name: form.full_name.trim() || null,
        bar_registration_number: form.bar_registration_number.trim() || null,
        jurisdiction: form.jurisdiction.trim() || null,
        years_experience: years === "" ? null : Number(years),
        practice_areas: splitList(form.practice_areas),
        languages: splitList(form.languages),
        location: form.location.trim() || null,
        bio: form.bio.trim() || null,
        consultation_modes: splitList(form.consultation_modes),
        fee_structure: form.fee_structure.trim() || null,
        availability: form.availability.trim() || null,
      })
      setFeedback("Profile saved.")
      refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save your profile.")
    } finally {
      setBusy(false)
    }
  }

  async function submitForVerification() {
    setBusy(true)
    setError(null)
    setFeedback(null)
    try {
      await submitLawyerVerification()
      setFeedback("Verification submission recorded.")
      refresh()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not submit for verification.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Lawyer profile</h1>
          <p className="text-sm text-muted-foreground">
            Practice details clients see when you accept their cases.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={status.variant}>{status.label}</Badge>
          <Badge variant={profile.profile_complete ? "success" : "outline"}>
            {profile.profile_complete ? "Profile complete" : "Profile incomplete"}
          </Badge>
        </div>
      </div>

      <Alert variant="info">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          <AlertTitle>Verification is recorded only, not reviewed</AlertTitle>
          <AlertDescription>
            There is no bar-registry check or human review workflow yet. Submitting marks your
            profile as “Pending review” for later processing and the platform does not claim your
            credentials are verified.
            {profile.verification_notes ? ` ${profile.verification_notes}` : ""}
          </AlertDescription>
        </div>
      </Alert>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {feedback ? (
        <Alert variant="success">
          <AlertDescription>{feedback}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Professional details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="full_name">Full name</Label>
            <Input
              id="full_name"
              value={form.full_name}
              onChange={(event) => update("full_name", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bar_registration_number">Bar registration number</Label>
            <Input
              id="bar_registration_number"
              value={form.bar_registration_number}
              onChange={(event) => update("bar_registration_number", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="jurisdiction">Jurisdiction</Label>
            <Input
              id="jurisdiction"
              value={form.jurisdiction}
              onChange={(event) => update("jurisdiction", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="years_experience">Years of experience</Label>
            <Input
              id="years_experience"
              type="number"
              min={0}
              value={form.years_experience}
              onChange={(event) => update("years_experience", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="practice_areas">Practice areas</Label>
            <Input
              id="practice_areas"
              placeholder="property, family"
              value={form.practice_areas}
              onChange={(event) => update("practice_areas", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="languages">Languages</Label>
            <Input
              id="languages"
              placeholder="English, Hindi"
              value={form.languages}
              onChange={(event) => update("languages", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="location">Location</Label>
            <Input
              id="location"
              value={form.location}
              onChange={(event) => update("location", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fee_structure">Fee structure</Label>
            <Input
              id="fee_structure"
              placeholder="Hourly / fixed / retainer"
              value={form.fee_structure}
              onChange={(event) => update("fee_structure", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="consultation_modes">Consultation modes</Label>
            <Input
              id="consultation_modes"
              placeholder="video, phone, in-person"
              value={form.consultation_modes}
              onChange={(event) => update("consultation_modes", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="availability">Availability</Label>
            <Input
              id="availability"
              placeholder="Weekdays 10:00–18:00"
              value={form.availability}
              onChange={(event) => update("availability", event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="bio">Professional bio</Label>
            <Textarea
              id="bio"
              value={form.bio}
              onChange={(event) => update("bio", event.target.value)}
              placeholder="Brief background and areas of focus."
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button variant="outline" disabled={busy} onClick={() => void submitForVerification()}>
          <ShieldCheck className="size-4" aria-hidden="true" />
          Submit for verification
        </Button>
        <Button disabled={busy} onClick={() => void save()}>
          <Save className="size-4" aria-hidden="true" />
          Save profile
        </Button>
      </div>
    </div>
  )
}
