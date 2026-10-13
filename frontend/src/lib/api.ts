import type { ApiErrorBody } from "@/lib/types"

const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL as string | undefined

export const API_BASE_URL = (RAW_BASE_URL ?? "http://localhost:8000/api").replace(/\/$/, "")

const AUTH_TOKEN_KEY = "juriscan-auth-token"

function readStoredToken(): string | null {
  try {
    return typeof localStorage !== "undefined" ? localStorage.getItem(AUTH_TOKEN_KEY) : null
  } catch {
    return null
  }
}

let authToken: string | null = readStoredToken()

export function getAuthToken(): string | null {
  return authToken
}

/** Persist (or clear) the session token used on every subsequent API request. */
export function setAuthToken(token: string | null) {
  authToken = token
  try {
    if (typeof localStorage === "undefined") return
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token)
    else localStorage.removeItem(AUTH_TOKEN_KEY)
  } catch {
    /* localStorage can be unavailable (e.g. private mode); keep the in-memory token */
  }
}

function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {}
}

export class ApiError extends Error {
  status: number
  code: string
  details?: unknown

  constructor(message: string, status: number, code = "request_failed", details?: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData

  let response: Response
  try {
    response = await fetch(url, {
      headers: {
        Accept: "application/json",
        ...authHeaders(),
        ...(init?.body && !isFormData ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      ...init,
    })
  } catch (error) {
    throw new ApiError(
      `Unable to reach the backend at ${API_BASE_URL}.`,
      0,
      "network_error",
      error,
    )
  }

  const isJson = response.headers.get("content-type")?.includes("application/json")
  const payload = isJson ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const body = payload as ApiErrorBody | null
    throw new ApiError(
      body?.error?.message ?? `Request failed with status ${response.status}.`,
      response.status,
      body?.error?.code ?? "request_failed",
      body?.error?.details,
    )
  }

  return payload as T
}

export interface UploadOptions extends RequestInit {
  onProgress?: (percent: number) => void
}

function uploadRequest<T>(path: string, formData: FormData, init?: UploadOptions): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`
  const { onProgress, ...rest } = init ?? {}

  if (typeof XMLHttpRequest === "undefined") {
    return request<T>(path, { ...rest, method: "POST", body: formData })
  }

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(rest.method ?? "POST", url, true)
    xhr.setRequestHeader("Accept", "application/json")
    if (authToken) {
      xhr.setRequestHeader("Authorization", `Bearer ${authToken}`)
    }

    xhr.upload.onprogress = (event) => {
      if (onProgress && event.lengthComputable && event.total > 0) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)))
      }
    }

    xhr.onload = () => {
      const isJson = xhr.getResponseHeader("content-type")?.includes("application/json")
      let payload: unknown = null
      if (isJson) {
        try {
          payload = JSON.parse(xhr.responseText)
        } catch {
          payload = null
        }
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100)
        resolve(payload as T)
        return
      }
      const body = payload as ApiErrorBody | null
      reject(
        new ApiError(
          body?.error?.message ?? `Request failed with status ${xhr.status}.`,
          xhr.status,
          body?.error?.code ?? "request_failed",
          body?.error?.details,
        ),
      )
    }

    xhr.onerror = () =>
      reject(new ApiError(`Unable to reach the backend at ${API_BASE_URL}.`, 0, "network_error"))
    xhr.ontimeout = () => reject(new ApiError("The upload timed out.", 0, "timeout_error"))

    xhr.send(formData)
  })
}

export const api = {
  get: <T>(path: string, init?: RequestInit) => request<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, { ...init, method: "POST", body: body ? JSON.stringify(body) : undefined }),
  delete: <T = void>(path: string, init?: RequestInit) =>
    request<T>(path, { ...init, method: "DELETE" }),
  put: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, { ...init, method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  upload: <T>(path: string, formData: FormData, init?: UploadOptions) =>
    uploadRequest<T>(path, formData, init),
}