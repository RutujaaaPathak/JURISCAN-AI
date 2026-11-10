import {
  AlertCircle,
  Building2,
  CheckCircle2,
  Lock,
  Shield,
  User,
} from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ErrorState } from "@/components/common/States"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { useToast } from "@/components/ui/toast"
import { setAuthToken } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { acceptInvitation, previewInvitation } from "@/lib/company"
import type { InvitationPreview } from "@/lib/company"
import { formatCompanyRole } from "@/lib/companyFilters"
import { formatDate } from "@/lib/format"

export function InvitationAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const { toast } = useToast()

  const [preview, setPreview] = useState<InvitationPreview | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(true)
  const [previewError, setPreviewError] = useState<string | null>(null)

  const [fullName, setFullName] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setPreviewError("No invitation token was supplied.")
      setLoadingPreview(false)
      return
    }

    let active = true
    previewInvitation(token)
      .then((data) => {
        if (!active) return
        setPreview(data)
      })
      .catch((err) => {
        if (!active) return
        setPreviewError(err instanceof Error ? err.message : "Invalid or expired invitation token.")
      })
      .finally(() => {
        if (active) setLoadingPreview(false)
      })

    return () => {
      active = false
    }
  }, [token])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSubmitting(true)
    setSubmitError(null)

    try {
      const result = (await acceptInvitation({
        token,
        password,
        full_name: preview?.account_exists ? undefined : fullName.trim(),
      })) as { access_token: string }

      if (result?.access_token) {
        setAuthToken(result.access_token)
        await refresh()
      }

      toast({
        title: "Welcome aboard!",
        description: `You have successfully joined ${preview?.company_name}.`,
      })

      navigate("/dashboard/company", { replace: true })
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not accept invitation.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center p-4">
      <Card className="w-full max-w-md border-border/80 bg-card/80 shadow-2xl backdrop-blur-md">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 text-primary">
            <Building2 className="size-6" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight text-foreground">
            Workspace Invitation
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground mt-1">
            Join your organization on JURISCAN-AI
          </CardDescription>
        </CardHeader>

        <CardContent>
          {loadingPreview ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3">
              <Spinner className="size-6 text-primary" />
              <p className="text-xs text-muted-foreground">Verifying invitation...</p>
            </div>
          ) : previewError ? (
            <div className="py-4 flex flex-col items-center gap-3">
              <ErrorState
                title="Invitation unavailable"
                description={previewError}
              />
              <Button asChild variant="outline" size="sm">
                <Link to="/login">Go to sign in</Link>
              </Button>
            </div>
          ) : preview ? (
            <div className="flex flex-col gap-5">
              {/* Preview Details */}
              <div className="rounded-lg border border-border/60 bg-muted/20 p-3.5 flex flex-col gap-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Company:</span>
                  <span className="font-semibold text-foreground">{preview.company_name}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Invited Email:</span>
                  <span className="font-mono text-foreground">{preview.email}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Assigned Role:</span>
                  <Badge variant="outline" className="border-primary/30 text-primary text-[10px]">
                    <Shield className="size-3 mr-1" />
                    {formatCompanyRole(preview.company_role)}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Expires:</span>
                  <span className="text-muted-foreground">{formatDate(preview.expires_at)}</span>
                </div>
              </div>

              {preview.status !== "PENDING" || preview.is_expired ? (
                <Alert className="border-red-500/30 bg-red-500/10 text-red-300">
                  <AlertCircle className="size-4 text-red-400" />
                  <AlertTitle className="text-xs font-semibold">Invitation Inactive</AlertTitle>
                  <AlertDescription className="text-xs">
                    This invitation has status{" "}
                    <strong className="text-foreground">{preview.status}</strong>. Please request a new invitation from your company administrator.
                  </AlertDescription>
                </Alert>
              ) : (
                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                  {submitError && (
                    <Alert className="border-red-500/30 bg-red-500/10 text-red-300 py-2.5">
                      <AlertCircle className="size-4 text-red-400" />
                      <AlertTitle className="text-xs font-semibold">Error</AlertTitle>
                      <AlertDescription className="text-xs">{submitError}</AlertDescription>
                    </Alert>
                  )}

                  {preview.account_exists ? (
                    <div className="rounded-md border border-primary/20 bg-primary/5 p-3 text-xs text-muted-foreground">
                      An account with <strong className="text-foreground font-mono">{preview.email}</strong> already exists.
                      Enter your password to link this account to <strong className="text-foreground">{preview.company_name}</strong>.
                    </div>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="fullname" className="text-xs font-medium text-foreground">
                        Your Full Name
                      </Label>
                      <div className="relative">
                        <User className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                        <Input
                          id="fullname"
                          required
                          placeholder="e.g. John Doe"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          className="pl-9 bg-background/50 text-sm h-9"
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="password" className="text-xs font-medium text-foreground">
                      {preview.account_exists ? "Your Account Password" : "Create Password (min. 8 characters)"}
                    </Label>
                    <div className="relative">
                      <Lock className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                      <Input
                        id="password"
                        type="password"
                        required
                        minLength={8}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="pl-9 bg-background/50 text-sm h-9"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={submitting || (!preview.account_exists && !fullName.trim()) || password.length < 8}
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90 mt-2 font-medium"
                  >
                    {submitting ? (
                      <Spinner className="size-4 mr-1.5" />
                    ) : (
                      <CheckCircle2 className="size-4 mr-1.5" />
                    )}
                    {preview.account_exists ? "Join Workspace" : "Create Account & Join"}
                  </Button>
                </form>
              )}
            </div>
          ) : null}
        </CardContent>

        <CardFooter className="flex justify-center border-t border-border/40 pt-4">
          <p className="text-xs text-muted-foreground">
            Already have an account?{" "}
            <Link to="/login" className="text-primary hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  )
}
export default InvitationAcceptPage
