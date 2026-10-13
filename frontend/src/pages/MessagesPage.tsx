import { Info, MessageSquare } from "lucide-react"

import { EmptyState } from "@/components/common/States"
import { Card, CardContent } from "@/components/ui/card"

export function MessagesPage() {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Messages</h1>
        <p className="text-sm text-muted-foreground">
          Keep conversations with your legal team and counterparties in one place.
        </p>
      </div>

      <Card>
        <CardContent className="flex items-start gap-3 py-1 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <p>
            Secure in-app messaging is not implemented yet. This area is reserved for a later
            release and shows no conversations or contacts.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <EmptyState
            icon={MessageSquare}
            title="No messages yet"
            description="When messaging is enabled, your conversations will be listed here."
          />
        </CardContent>
      </Card>
    </div>
  )
}
