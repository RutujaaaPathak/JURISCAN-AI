import type { FormEvent } from "react"
import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { dashboardPathForRole } from "@/lib/roles"

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const requested = (location.state as { from?: string } | null)?.from
  const redirectTo =
    requested && requested.startsWith("/dashboard") ? requested : null

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const current = await login(email.trim(), password)
      navigate(redirectTo ?? dashboardPathForRole(current.role), { replace: true })
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not sign you in.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      description="Sign in to your JurisScan-AI workspace."
      footer={
        <>
          New to JurisScan-AI?{" "}
          <Link className="font-medium text-primary hover:underline" to="/signup">
            Create an account
          </Link>
        </>
      }
    >
      <Card className="surface-panel rounded-2xl border border-white/10 shadow-2xl backdrop-blur-xl">
        <CardContent className="pt-6">
          <form className="flex flex-col gap-4" onSubmit={submit} noValidate>
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Sign-in failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="bg-background/60 border-white/10 focus-visible:border-primary"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="bg-background/60 border-white/10 focus-visible:border-primary"
              />
            </div>

            <Button type="submit" disabled={busy} className="btn-gold-primary h-10 w-full mt-2 font-semibold">
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </AuthLayout>
  )
}
