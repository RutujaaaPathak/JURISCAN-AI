/**
 * Pure request-header helpers.
 *
 * Kept free of any runtime imports (no `import.meta.env`, no DOM) so they can be
 * unit tested with `node --test` (see `apiHeaders.test.ts`). Both the JSON API
 * client and the binary report download build their auth header here, so the two
 * paths can never drift apart.
 */

export function bearerHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Headers for the analysis-report download.
 *
 * The report endpoint is authenticated like every other API call, but a Blob
 * download cannot go through the JSON `api` helper, so the bearer token must be
 * attached explicitly here. Omitting it made the backend fall back to the dev
 * demo workspace user, which does not own the signed-in user's documents - the
 * root cause of the "Document N was not found" export failure.
 */
export function reportRequestHeaders(token: string | null): Record<string, string> {
  return { Accept: "application/pdf", ...bearerHeaders(token) }
}
