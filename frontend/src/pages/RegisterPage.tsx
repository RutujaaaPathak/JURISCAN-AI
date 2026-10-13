import type { FormEvent } from "react"
import { useState } from "react"
import { Link, Navigate, useNavigate, useParams } from "react-router-dom"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ApiError } from "@/lib/api"
import { isPublicRole, useAuth } from "@/lib/auth"
import type { RegisterPayload } from "@/lib/auth"
import { ROLE_META } from "@/lib/roles"

interface FormState {
  full_name: string
  organization_name: string
  email: string
  password: string
  confirm: string
  bar_registration_number: string
  jurisdiction: string
  years_experience: string
  practice_areas: string
  languages: string
  location: string
  bio: string
}

const EMPTY: FormState = {
  full_name: "",
  organization_name: "",
  email: "",
  password: "",
  confirm: "",
  bar_registration_number: "",
  jurisdiction: "",
  years_experience: "",
  practice_areas: "",
  languages: "",
  location: "",
  bio: "",
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)
}

export function RegisterPage() {
  const { role } = useParams<{ role: string }>()
  const { register } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState<FormState>(EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isPublicRole(role)) {
    return <Navigate to="/signup" replace />
  }

  const publicRole: "individual" | "company" | "lawyer" = role
  const isCompany = publicRole === "company"
  const isLawyer = publicRole === "lawyer"

  function update<K extends keyof FormState>(key: K, value: string) {
    setForm((previous) => ({ ...previous, [key]: value }))
  }

  function buildPayload(): RegisterPayload | string {
    if (form.password !== form.confirm) {
      return "Passwords do not match."
    }
    if (form.password.length < 8) {
      return "Password must be at least 8 characters."
    }

    const payload: RegisterPayload = {
      role: publicRole,
      email: form.email.trim(),
      password: form.password,
      full_name: form.full_name.trim(),
    }

    if (isCompany) {
      payload.organization_name = form.organization_name.trim()
    }

    if (isLawyer) {
      const years = form.years_experience.trim()
      payload.bar_registration_number = form.bar_registration_number.trim()
      payload.jurisdiction = form.jurisdiction.trim()
      payload.years_experience = years === "" ? undefined : Number(years)
      payload.practice_areas = splitList(form.practice_areas)
      payload.languages = splitList(form.languages)
      payload.location = form.location.trim() || undefined
      payload.bio = form.bio.trim()
    }

    return payload
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const payload = buildPayload()
    if (typeof payload === "string") {
      setError(payload)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await register(payload)
      navigate("/dashboard", { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not create your account.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      wide
      title={`Sign up as ${ROLE_META[role].label.toLowerCase()}`}
      description={ROLE_META[role].description}
      footer={
        <>
          Already have an account?{" "}
          <Link className="font-medium text-primary hover:underline" to="/login">
            Sign in
          </Link>
          <span className="mx-2 text-border">·</span>
          <Link className="font-medium text-primary hover:underline" to="/signup">
            Change role
          </Link>
        </>
      }
    >
      <Card>
        <CardContent className="pt-6">
          <form className="flex flex-col gap-4" onSubmit={submit} noValidate>
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Could not create account</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2">
              {isCompany ? (
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                  <Label htmlFor="organization_name">Company name</Label>
                  <Input
                    id="organization_name"
                    required
                    value={form.organization_name}
                    onChange={(event) => update("organization_name", event.target.value)}
                  />
                </div>
              ) : null}

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="full_name">{isCompany ? "Contact name" : "Full name"}</Label>
                <Input
                  id="full_name"
                  required
                  value={form.full_name}
                  onChange={(event) => update("full_name", event.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Work email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={form.email}
                  onChange={(event) => update("email", event.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={form.password}
                  onChange={(event) => update("password", event.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="confirm">Confirm password</Label>
                <Input
                  id="confirm"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={form.confirm}
                  onChange={(event) => update("confirm", event.target.value)}
                />
              </div>
            </div>

            {isLawyer ? (
              <div className="flex flex-col gap-4 border-t border-border pt-4">
                <p className="text-sm font-semibold">Professional details</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="bar_registration_number">Bar registration number</Label>
                    <Input
                      id="bar_registration_number"
                      required
                      value={form.bar_registration_number}
                      onChange={(event) => update("bar_registration_number", event.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="jurisdiction">Jurisdiction</Label>
                    <Input
                      id="jurisdiction"
                      required
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
                      required
                      value={form.years_experience}
                      onChange={(event) => update("years_experience", event.target.value)}
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
                    <Label htmlFor="practice_areas">Practice areas</Label>
                    <Input
                      id="practice_areas"
                      required
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
                  <div className="flex flex-col gap-1.5 sm:col-span-2">
                    <Label htmlFor="bio">Professional bio</Label>
                    <Textarea
                      id="bio"
                      required
                      value={form.bio}
                      onChange={(event) => update("bio", event.target.value)}
                      placeholder="Brief background and areas of focus."
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Your profile starts as unverified. Verification review is not automated yet, so
                  nothing is presented to clients as independently verified.
                </p>
              </div>
            ) : null}

            <Button type="submit" disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthLayout>
  )
}
