/**
 * Pure STUN/TURN configuration builder.
 *
 * Kept free of runtime imports so it can be unit tested with `node --test`.
 * Production TURN credentials must be supplied through Vite environment
 * variables; nothing secret is hardcoded here.
 */

export interface IceServerEnv {
  stunServer?: string
  turnServer?: string
  turnUsername?: string
  turnCredential?: string
}

const DEFAULT_STUN_SERVER = "stun:stun.l.google.com:19302"

export function buildIceServers(env: IceServerEnv): RTCConfiguration {
  const stunServer = env.stunServer?.trim() || DEFAULT_STUN_SERVER
  const iceServers: RTCIceServer[] = [{ urls: stunServer }]

  const turnServer = env.turnServer?.trim()
  if (turnServer) {
    const turn: RTCIceServer = { urls: turnServer }
    const username = env.turnUsername?.trim()
    const credential = env.turnCredential?.trim()
    if (username) turn.username = username
    if (credential) turn.credential = credential
    iceServers.push(turn)
  }

  return { iceServers }
}
