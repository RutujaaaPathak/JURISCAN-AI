import { Gavel, Info } from "lucide-react"

import { EmptyState } from "@/components/common/States"
import { Card, CardContent } from "@/components/ui/card"

export function LegalHelpPage() {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Find legal help &amp; my cases</h1>
        <p className="text-sm text-muted-foreground">
          Connect with legal professionals and keep track of active matters.
        </p>
      </div>

      <Card>
        <CardContent className="flex items-start gap-3 py-1 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            The legal-help directory and case management are not implemented yet. This area is
            reserved for a later release and currently stores no cases.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <EmptyState
            icon={Gavel}
            title="No cases yet"
            description="Once case management is available, your matters and matching legal professionals will appear here."
          />
        </CardContent>
      </Card>
    </div>
  )
}
