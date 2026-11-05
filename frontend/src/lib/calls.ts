import { api } from "@/lib/api"
import { buildIceServers } from "@/lib/iceServers"
import type { ActiveCallResponse, CallListResponse, CallRead } from "@/lib/types"

/**
 * Configure STUN and optional TURN servers via environment variables.
 * Production credentials must never be hardcoded in client source code.
 */
export function getIceServers(): RTCConfiguration {
  return buildIceServers({
    stunServer: import.meta.env.VITE_WEBRTC_STUN_SERVER as string | undefined,
    turnServer: import.meta.env.VITE_WEBRTC_TURN_SERVER as string | undefined,
    turnUsername: import.meta.env.VITE_WEBRTC_TURN_USERNAME as string | undefined,
    turnCredential: import.meta.env.VITE_WEBRTC_TURN_CREDENTIAL as string | undefined,
  })
}

export async function initiateCall(caseId: string | number): Promise<CallRead> {
  return api.post<CallRead>(`/cases/${caseId}/calls`)
}

export async function getCallHistory(
  caseId: string | number,
  limit = 50,
  offset = 0,
): Promise<CallListResponse> {
  return api.get<CallListResponse>(`/cases/${caseId}/calls?limit=${limit}&offset=${offset}`)
}

export async function getActiveCall(caseId: string | number): Promise<ActiveCallResponse> {
  return api.get<ActiveCallResponse>(`/cases/${caseId}/calls/active`)
}

export async function getCallDetail(
  caseId: string | number,
  callId: number,
): Promise<CallRead> {
  return api.get<CallRead>(`/cases/${caseId}/calls/${callId}`)
}

export async function acceptCall(
  caseId: string | number,
  callId: number,
): Promise<CallRead> {
  return api.post<CallRead>(`/cases/${caseId}/calls/${callId}/accept`)
}

export async function rejectCall(
  caseId: string | number,
  callId: number,
  reason?: string,
): Promise<CallRead> {
  const query = reason ? `?reason=${encodeURIComponent(reason)}` : ""
  return api.post<CallRead>(`/cases/${caseId}/calls/${callId}/reject${query}`)
}

export async function endCall(
  caseId: string | number,
  callId: number,
  reason?: string,
): Promise<CallRead> {
  const query = reason ? `?reason=${encodeURIComponent(reason)}` : ""
  return api.post<CallRead>(`/cases/${caseId}/calls/${callId}/end${query}`)
}

/**
 * Format duration in seconds to a human-readable mm:ss string.
 */
export function formatCallDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds) || seconds < 0) return "00:00"
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  const pad = (n: number) => n.toString().padStart(2, "0")
  return `${pad(mins)}:${pad(secs)}`
}

export function callStatusMeta(status: string): {
  label: string
  variant: "success" | "destructive" | "warning" | "outline"
} {
  switch (status) {
    case "ACCEPTED":
      return { label: "Answered", variant: "success" }
    case "ENDED":
      return { label: "Completed", variant: "outline" }
    case "RINGING":
      return { label: "Ringing", variant: "warning" }
    case "REJECTED":
      return { label: "Declined", variant: "destructive" }
    case "MISSED":
      return { label: "Missed", variant: "destructive" }
    case "FAILED":
      return { label: "Failed", variant: "destructive" }
    default:
      return { label: status, variant: "outline" }
  }
}

