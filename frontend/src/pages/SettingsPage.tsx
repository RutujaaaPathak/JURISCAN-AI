import { Bell, Save, SlidersHorizontal, User } from "lucide-react"
import { useState } from "react"

import { DemoNotice } from "@/components/common/DemoNotice"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/components/ui/toast"

export function SettingsPage() {
  const { toast } = useToast()
  const [profile, setProfile] = useState({
    name: "Priya Raman",
    email: "priya.raman@juriscan.ai",
    organisation: "JurisScan Legal",
    jurisdiction: "England & Wales",
  })
  const [prefs, setPrefs] = useState({
    threshold: "medium",
    autoAnalyze: true,
    model: "legal-bert",
  })
  const [notifications, setNotifications] = useState({
    emailDigest: true,
    highRisk: true,
    weeklyReport: false,
  })

  const save = (section: string) => {
    toast({
      title: `${section} saved`,
      description: "Preferences are stored in this session only — no backend yet.",
      variant: "success",
    })
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your profile, analysis and notification preferences.</p>
      </div>

      <DemoNotice text="Settings are interactive but are not persisted — there is no settings API yet." />

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
                value={profile.name}
                onChange={(event) => setProfile({ ...profile, name: event.target.value })}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Work email</Label>
              <Input
                id="email"
                type="email"
                value={profile.email}
                onChange={(event) => setProfile({ ...profile, email: event.target.value })}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="organisation">Organisation</Label>
              <Input
                id="organisation"
                value={profile.organisation}
                onChange={(event) => setProfile({ ...profile, organisation: event.target.value })}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="jurisdiction">Primary jurisdiction</Label>
              <Input
                id="jurisdiction"
                value={profile.jurisdiction}
                onChange={(event) => setProfile({ ...profile, jurisdiction: event.target.value })}
              />
            </div>
          </div>
          <div className="flex justify-end">
            <Button size="sm" onClick={() => save("Profile")}>
              <Save className="size-4" aria-hidden="true" />
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
                onChange={(event) => setPrefs({ ...prefs, threshold: event.target.value })}
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
                onChange={(event) => setPrefs({ ...prefs, model: event.target.value })}
              >
                <option value="legal-bert">Legal-BERT (planned)</option>
                <option value="rules">Rule-based baseline</option>
                <option value="heuristic">Heuristic demo</option>
              </Select>
            </div>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
            <div>
              <p className="text-sm font-medium">Analyze on upload</p>
              <p className="text-xs text-muted-foreground">Start analysis automatically when a document is added.</p>
            </div>
            <Switch
              checked={prefs.autoAnalyze}
              onCheckedChange={(checked) => setPrefs({ ...prefs, autoAnalyze: checked })}
              aria-label="Analyze on upload"
            />
          </div>
          <div className="flex justify-end">
            <Button size="sm" onClick={() => save("Analysis preferences")}>
              <Save className="size-4" aria-hidden="true" />
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
                onCheckedChange={(checked) => setNotifications({ ...notifications, [item.key]: checked })}
                aria-label={item.title}
              />
            </div>
          ))}
          <div className="flex justify-end">
            <Button size="sm" onClick={() => save("Notification settings")}>
              <Save className="size-4" aria-hidden="true" />
              Save notifications
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
