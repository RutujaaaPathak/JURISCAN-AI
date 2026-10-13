import { AlertTriangle, CheckCircle2, FileText, Upload } from "lucide-react"

import type { ActivityItem } from "@/components/dashboard/ActivityFeed"
import type { DocumentSummary } from "@/lib/types"

/**
 * Derives a chronological activity trail from real document records. Only facts
 * present on the document are used (upload, extraction, failure, analysis), so
 * the feed never fabricates events.
 */
export function buildActivity(items: DocumentSummary[]): ActivityItem[] {
  const events: ActivityItem[] = []
  for (const doc of items) {
    events.push({
      id: `upload-${doc.id}`,
      title: "Document uploaded",
      description: doc.title,
      timestamp: doc.created_at,
      icon: Upload,
      tone: "default",
    })
    if (doc.extracted_at) {
      events.push({
        id: `extract-${doc.id}`,
        title: "Text extracted",
        description: doc.title,
        timestamp: doc.extracted_at,
        icon: FileText,
        tone: "default",
      })
    }
    if (doc.status === "FAILED") {
      events.push({
        id: `failed-${doc.id}`,
        title: "Processing failed",
        description: doc.error_message ?? doc.title,
        timestamp: doc.updated_at,
        icon: AlertTriangle,
        tone: "destructive",
      })
    } else if (doc.status === "PROCESSED") {
      events.push({
        id: `analyzed-${doc.id}`,
        title: "Analysis completed",
        description:
          doc.risk_score !== null
            ? `${doc.title} · risk ${Math.round(doc.risk_score)}/100`
            : doc.title,
        timestamp: doc.updated_at,
        icon: CheckCircle2,
        tone: "success",
      })
    }
  }
  return events
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 6)
}
