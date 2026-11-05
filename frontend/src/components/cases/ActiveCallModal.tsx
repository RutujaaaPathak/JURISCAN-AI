import {
  AlertCircle,
  Loader2,
  Mic,
  MicOff,
  Phone,
  PhoneIncoming,
  PhoneOff,
  User,
} from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { VoiceCallController } from "@/hooks/useVoiceCall"
import { useAuth } from "@/lib/auth"
import { otherPartyName } from "@/lib/callState"
import { formatCallDuration } from "@/lib/calls"

interface ActiveCallModalProps {
  controller: VoiceCallController
  caseTitle?: string
}

export function ActiveCallModal({ controller, caseTitle }: ActiveCallModalProps) {
  const { user } = useAuth()
  const {
    activeCall,
    incomingCall,
    callState,
    isMuted,
    duration,
    remoteAudioRef,
    error,
    acceptIncomingCall,
    rejectIncomingCall,
    endActiveCall,
    toggleMute,
    clearError,
  } = controller

  // Remote audio output element for browser-to-browser WebRTC stream
  const audioElement = (
    <audio
      ref={remoteAudioRef}
      autoPlay
      playsInline
      className="sr-only"
      aria-hidden="true"
    />
  )

  // 1. Incoming Call Dialog
  if (incomingCall) {
    const callerLabel = otherPartyName(incomingCall, user?.id ?? null)
    const isAccepting =
      callState === "requesting_permission" || callState === "connecting"
    return (
      <>
        {audioElement}
        <Dialog
          open={true}
          onOpenChange={(open) => {
            if (!open) void rejectIncomingCall()
          }}
        >
          <DialogContent className="max-w-md sm:max-w-md">
            <DialogHeader className="items-center text-center">
              <div className="mb-2 flex size-16 items-center justify-center rounded-full bg-primary/10 text-primary animate-pulse">
                <PhoneIncoming className="size-8" />
              </div>
              <DialogTitle className="text-xl">Incoming Voice Call</DialogTitle>
              <DialogDescription>
                <span className="font-medium text-foreground">{callerLabel}</span> is calling
                you regarding {caseTitle ? `“${caseTitle}”` : "this case"}.
              </DialogDescription>
            </DialogHeader>

            {error ? (
              <Alert variant="destructive" className="mt-2">
                <AlertCircle className="size-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <div className="mt-6 flex items-center justify-center gap-6">
              <Button
                variant="destructive"
                size="lg"
                className="flex items-center gap-2 rounded-full px-6 shadow-lg"
                disabled={isAccepting}
                onClick={() => void rejectIncomingCall()}
              >
                <PhoneOff className="size-5" />
                Decline
              </Button>
              <Button
                variant="default"
                size="lg"
                className="flex items-center gap-2 rounded-full bg-emerald-600 px-6 text-white shadow-lg hover:bg-emerald-700"
                disabled={isAccepting}
                onClick={() => void acceptIncomingCall()}
              >
                {isAccepting ? (
                  <Loader2 className="size-5 animate-spin" />
                ) : (
                  <Phone className="size-5" />
                )}
                Accept
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </>
    )
  }

  // 2. Active Outgoing or Connected Call Dialog
  const isInCall =
    callState === "calling" ||
    callState === "ringing" ||
    callState === "connecting" ||
    callState === "connected" ||
    callState === "requesting_permission"

  if (!isInCall && !error) {
    return audioElement
  }

  const otherPersonName = otherPartyName(activeCall, user?.id ?? null)

  return (
    <>
      {audioElement}
      <Dialog open={isInCall || !!error} onOpenChange={(open) => !open && clearError()}>
        <DialogContent className="max-w-sm sm:max-w-sm">
          <DialogHeader className="items-center text-center">
            <div className="relative mb-3 flex size-20 items-center justify-center rounded-full bg-primary/10 text-primary">
              <User className="size-10" />
              {callState === "connected" ? (
                <span className="absolute bottom-1 right-1 flex size-4 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-background">
                  <span className="size-2 rounded-full bg-white animate-ping" />
                </span>
              ) : null}
            </div>
            <DialogTitle className="text-lg">{otherPersonName}</DialogTitle>
            <DialogDescription className="flex items-center justify-center gap-2">
              {caseTitle ? `Case: ${caseTitle}` : "Voice Call"}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col items-center gap-3 py-2">
            {callState === "requesting_permission" ? (
              <Badge variant="outline" className="flex items-center gap-1.5 py-1 text-xs">
                <Loader2 className="size-3 animate-spin" />
                Requesting mic access…
              </Badge>
            ) : callState === "calling" || callState === "ringing" ? (
              <Badge variant="warning" className="flex items-center gap-1.5 py-1 text-xs">
                <Loader2 className="size-3 animate-spin" />
                Ringing…
              </Badge>
            ) : callState === "connecting" ? (
              <Badge variant="warning" className="flex items-center gap-1.5 py-1 text-xs">
                <Loader2 className="size-3 animate-spin" />
                Connecting peer…
              </Badge>
            ) : callState === "connected" ? (
              <div className="flex flex-col items-center gap-1">
                <Badge variant="success" className="py-1 text-xs">
                  Connected
                </Badge>
                <span className="font-mono text-2xl font-bold tracking-wider text-foreground">
                  {formatCallDuration(duration)}
                </span>
              </div>
            ) : (
              <Badge variant="outline" className="py-1 text-xs">
                Call ended
              </Badge>
            )}

            {error ? (
              <Alert variant="destructive" className="w-full text-xs">
                <AlertCircle className="size-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
          </div>

          <div className="mt-4 flex items-center justify-center gap-4">
            {callState === "connected" ? (
              <Button
                variant={isMuted ? "destructive" : "outline"}
                size="icon"
                className="size-12 rounded-full"
                title={isMuted ? "Unmute microphone" : "Mute microphone"}
                onClick={toggleMute}
              >
                {isMuted ? <MicOff className="size-5" /> : <Mic className="size-5" />}
              </Button>
            ) : null}

            {isInCall ? (
              <Button
                variant="destructive"
                size="icon"
                className="size-12 rounded-full shadow-md"
                title="End Call"
                onClick={() => void endActiveCall()}
              >
                <PhoneOff className="size-5" />
              </Button>
            ) : (
              <Button
                variant="outline"
                className="rounded-full px-5"
                onClick={clearError}
              >
                Dismiss
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

