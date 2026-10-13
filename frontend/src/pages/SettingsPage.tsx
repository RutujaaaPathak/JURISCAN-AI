import { Bell, RefreshCw, Save, SlidersHorizontal, User } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/components/ui/toast"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import {
  getSettings,
  updateSettings,
  type AnalysisModel,
  type SeverityLevel,
  type UserSettings,
  type UserSettingsUpdate,
} from "@/lib/settings"

type LoadStatus = "loading" | "ready" | "error"
type Section = "profile" | "preferences" | "notifications"

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return "Something went wrong."
}

export function SettingsPage() {
  const { refresh } = useAuth()
  const { toast } = useToast()

  const [status, setStatus] = useState<LoadStatus>("loading")
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState<Section | null>(null)

  const [profile, setProfile] = useState({
    fullName: "",
    email: "",
    organization: "",
    jurisdiction: "",
  })
  const [canEditOrganization, setCanEditOrganization] = useState(false)
  const [prefs, setPrefs] = useState<{
    threshold: SeverityLevel
    autoAnalyze: boolean
    model: AnalysisModel
  }>({ threshold: "medium", autoAnalyze: true, model: "rules" })
  const [notifications, setNotifications] = useState({
    emailDigest: true,
    highRisk: true,
    weeklyReport: false,
  })

  // Single place that maps server state into the form, so a failed save never
  // leaves the UI showing values the backend did not accept.
  const applySettings = useCallback((settings: UserSettings) => {
    setProfile({
      fullName: settings.full_name ?? "",
      email: settings.email,
      organization: settings.organization_name ?? "",
      jurisdiction: settings.jurisdiction ?? "",
    })
    setCanEditOrganization(settings.role === "company")
    setPrefs({
      threshold: settings.min_severity,
      autoAnalyze: settings.auto_analyze,
      model: settings.analysis_model,
    })
    setNotifications({
      emailDigest: settings.notify_email_digest,
      highRisk: settings.notify_high_risk,
      weeklyReport: settings.notify_weekly_report,
    })
  }, [])

  const load = useCallback(() => {
    setStatus("loading")
    setLoadError(null)
    getSettings()
      .then((settings) => {
        applySettings(settings)
        setStatus("ready")
      })
      .catch((error) => {
        setLoadError(errorText(error))
        setStatus("error")
      })
  }, [applySettings])

  useEffect(() => {
    load()
  }, [load])

  const saveSection = useCallback(
    async (section: Section, label: string, payload: UserSettingsUpdate) => {
      setSaving(section)
      try {
        const settings = await updateSettings(payload)
        applySettings(settings)
        if (section === "profile") {
          await refresh()
        }
        toast({ title: `${label} saved`, variant: "success" })
      } catch (error) {
        // Only a resolved backend response shows success; failures surface here.
        toast({
          title: `Could not save ${label.toLowerCase()}`,
          description: errorText(error),
          variant: "destructive",
        })
      } finally {
        setSaving(null)
      }
    },
    [applySettings, refresh, toast],
  )

  const heading = (
    <div className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <p className="text-sm text-muted-foreground">
        Manage your profile, analysis and notification preferences.
      </p>
    </div>
  )

  if (status === "loading") {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        {heading}
        <Card>
          <CardContent className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Spinner />
            Loading your settings…
          </CardContent>
        </Card>
      </div>
    )
  }

  if (status === "error") {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        {heading}
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="text-sm text-destructive">
              We couldn&apos;t load your settings. {loadError}
            </p>
            <Button size="sm" variant="outline" onClick={load}>
              <RefreshCw className="size-4" aria-hidden="true" />
              Try again
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      {heading}

      <Card>
        <CardHeader className="flex-row items-center gap-2">
          <User className="size-4 text-muted-foreground" aria-hidden="true" />
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="name">Full name</Label>
              <Input
                id="name"
                value={profile.fullName}
                placeholder="Add your full name"
                onChange={(event) => setProfile({ ...profile, fullName: event.target.value })}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={profile.email}
                readOnly
                disabled
                aria-describedby="email-help"
                className="bg-muted"
              />
              <p id="email-help" className="text-xs text-muted-foreground">
                Your email identifies your account and can&apos;t be changed here.
              </p>
            </div>
            {canEditOrganization ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="organisation">Organisation</Label>
                <Input
                  id="organisation"
                  value={profile.organization}
                  placeholder="Your organisation"
                  onChange={(event) => setProfile({ ...profile, organization: event.target.value })}
                />
              </div>
            ) : null}
            <div className="flex flex-col gap-2">
              <Label htmlFor="jurisdiction">Primary jurisdiction</Label>
              <Input
                id="jurisdiction"
                value={profile.jurisdiction}
                placeholder="e.g. India — Maharashtra"
                onChange={(event) => setProfile({ ...profile, jurisdiction: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">Leave blank if not applicable.</p>
            </div>
          </div>
          <div className="flex justify-end">
            <Button
              size="sm"
              disabled={saving !== null}
              onClick={() =>
                saveSection("profile", "Profile", {
                  full_name: profile.fullName,
                  jurisdiction: profile.jurisdiction,
                  ...(canEditOrganization ? { organization_name: profile.organization } : {}),
                })
              }
            >
              {saving === "profile" ? <Spinner /> : <Save className="size-4" aria-hidden="true" />}
              Save profile
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center gap-2">
          <SlidersHorizontal className="size-4 text-muted-foreground" aria-hidden="true" />
          <CardTitle>Analysis preferences</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="threshold">Minimum severity to surface</Label>
              <Select
                id="threshold"
                value={prefs.threshold}
                onChange={(event) =>
                  setPrefs({ ...prefs, threshold: event.target.value as SeverityLevel })
                }
              >
                <option value="low">Low and above</option>
                <option value="medium">Medium and above</option>
                <option value="high">High and above</option>
                <option value="critical">Critical only</option>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="model">Analysis model</Label>
              <Select
                id="model"
                value={prefs.model}
                onChange={(event) => setPrefs({ ...prefs, model: event.target.value as AnalysisModel })}
              >
                <option value="rules">Rule-based baseline</option>
                <option value="heuristic">Heuristic demo</option>
                <option value="legal-bert">Legal-BERT (planned)</option>
              </Select>
            </div>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div>
              <p className="text-sm font-medium">Analyze on upload</p>
              <p className="text-xs text-muted-foreground">
                Start analysis automatically when a document is added.
              </p>
            </div>
            <Switch
              checked={prefs.autoAnalyze}
              onCheckedChange={(checked) => setPrefs({ ...prefs, autoAnalyze: checked })}
              aria-label="Analyze on upload"
            />
          </div>
          <div className="flex justify-end">
            <Button
              size="sm"
              disabled={saving !== null}
              onClick={() =>
                saveSection("preferences", "Analysis preferences", {
                  min_severity: prefs.threshold,
                  analysis_model: prefs.model,
                  auto_analyze: prefs.autoAnalyze,
                })
              }
            >
              {saving === "preferences" ? (
                <Spinner />
              ) : (
                <Save className="size-4" aria-hidden="true" />
              )}
              Save preferences
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center gap-2">
          <Bell className="size-4 text-muted-foreground" aria-hidden="true" />
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {(
            [
              { key: "emailDigest", title: "Email digest", detail: "Daily summary of completed analyses." },
              { key: "highRisk", title: "High-risk alerts", detail: "Immediate alert when critical findings are detected." },
              { key: "weeklyReport", title: "Weekly report", detail: "Portfolio risk report every Monday." },
            ] as const
          ).map((item) => (
            <div
              key={item.key}
              className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
            >
              <div>
                <p className="text-sm font-medium">{item.title}</p>
                <p className="text-xs text-muted-foreground">{item.detail}</p>
              </div>
              <Switch
                checked={notifications[item.key]}
                onCheckedChange={(checked) =>
                  setNotifications({ ...notifications, [item.key]: checked })
                }
                aria-label={item.title}
              />
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            Preferences are saved to your account. Outbound email delivery isn&apos;t enabled yet, so
            these toggles record your intent only.
          </p>
          <div className="flex justify-end">
            <Button
              size="sm"
              disabled={saving !== null}
              onClick={() =>
                saveSection("notifications", "Notification settings", {
                  notify_email_digest: notifications.emailDigest,
                  notify_high_risk: notifications.highRisk,
                  notify_weekly_report: notifications.weeklyReport,
                })
              }
            >
              {saving === "notifications" ? (
                <Spinner />
              ) : (
                <Save className="size-4" aria-hidden="true" />
              )}
              Save notifications
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
