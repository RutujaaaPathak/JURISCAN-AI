import { Activity, Database, Server, ShieldCheck } from "lucide-react"

import { ErrorState, LoadingState } from "@/components/common/States"
import { PageHeader } from "@/components/layout/PageHeader"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useHealth } from "@/hooks/useHealth"
import { useStatus } from "@/hooks/useStatus"
import { API_BASE_URL } from "@/lib/api"

/**
 * Admin overview. It reports only live backend/database status from the public
 * endpoints — no invented governance metrics. The management surfaces shown in
 * the sidebar (team management, audit log) are not implemented yet.
 */
export function AdminDashboardPage() {
  const { state: health, refresh: refreshHealth } = useHealth()
  const { state: status, refresh: refreshStatus } = useStatus()

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <PageHeader
        title="Administration"
        description="Platform status and governance overview."
      />

      <Alert variant="info">
        <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          <AlertTitle>Admin tooling is not implemented yet</AlertTitle>
          <AlertDescription>
            Team management, audit logs and lawyer verification review are planned but not built.
            This page only surfaces live platform status.
          </AlertDescription>
        </div>
      </Alert>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Live system status</CardTitle>
          <Badge variant="outline">
            <Server className="size-3" aria-hidden="true" />
            {API_BASE_URL}
          </Badge>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-border p-4">
            <p className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Activity className="size-4 text-muted-foreground" aria-hidden="true" />
              Backend
            </p>
            {health.phase === "loading" || health.phase === "idle" ? (
              <LoadingState label="Contacting backend…" />
            ) : health.phase === "error" ? (
              <ErrorState
                title="Backend unreachable"
                description={health.error ?? undefined}
                onRetry={() => void refreshHealth()}
              />
            ) : (
              <dl className="flex flex-col gap-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="font-medium capitalize">{health.data?.status}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Environment</dt>
                  <dd className="font-medium">{health.data?.environment}</dd>
                </div>
              </dl>
            )}
          </div>

          <div className="rounded-lg border border-border p-4">
            <p className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Database className="size-4 text-muted-foreground" aria-hidden="true" />
              Database
            </p>
            {status.phase === "loading" || status.phase === "idle" ? (
              <LoadingState label="Checking services…" />
            ) : status.phase === "error" ? (
              <ErrorState
                title="Status unavailable"
                description={status.error ?? undefined}
                onRetry={() => void refreshStatus()}
              />
            ) : (
              <dl className="flex flex-col gap-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Overall</dt>
                  <dd className="font-medium capitalize">{status.data?.status}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-muted-foreground">Connection</dt>
                  <dd>
                    <Badge variant={status.data?.database === "ok" ? "success" : "destructive"}>
                      {status.data?.database ?? "unknown"}
                    </Badge>
                  </dd>
                </div>
              </dl>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
