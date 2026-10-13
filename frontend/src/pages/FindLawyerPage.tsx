import { BadgeCheck, MapPin, Search, Scale, Star } from "lucide-react"
import { useCallback, useState } from "react"
import { useNavigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { useAsync } from "@/hooks/useAsync"
import { CASE_CATEGORY_OPTIONS, caseCategoryLabel } from "@/lib/caseFilters"
import {
  CONSULTATION_MODE_OPTIONS,
  EXPERIENCE_OPTIONS,
  consultationModeLabel,
  experienceLabel,
  initials,
  verificationLabel,
} from "@/lib/lawyerFilters"
import { listLawyers } from "@/lib/lawyers"
import type { LawyerDirectoryEntry } from "@/lib/types"

const PAGE_SIZE = 12

function VerifiedBadge({ status }: { status: string }) {
  if (status === "VERIFIED") {
    return (
      <Badge variant="success">
        <BadgeCheck className="size-3" aria-hidden="true" />
        Verified
      </Badge>
    )
  }
  return <Badge variant="outline">{verificationLabel(status)}</Badge>
}

function LawyerCard({
  entry,
  onOpen,
  onRequest,
}: {
  entry: LawyerDirectoryEntry
  onOpen: () => void
  onRequest: () => void
}) {
  return (
    <Card className="flex flex-col">
      <CardContent className="flex flex-1 flex-col gap-3">
        <div className="flex items-start gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
            {initials(entry.full_name)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{entry.full_name ?? "Unnamed lawyer"}</p>
            <p className="flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="size-3" aria-hidden="true" />
              {entry.location ?? entry.jurisdiction ?? "Location not stated"}
            </p>
          </div>
          <VerifiedBadge status={entry.verification_status} />
        </div>

        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Star className="size-3.5" aria-hidden="true" />
          {experienceLabel(entry.years_experience)}
        </p>

        <div className="flex flex-wrap gap-1.5">
          {entry.practice_areas.length > 0 ? (
            entry.practice_areas.slice(0, 3).map((area) => (
              <Badge key={area} variant="secondary">
                {caseCategoryLabel(area)}
              </Badge>
            ))
          ) : (
            <span className="text-xs text-muted-foreground">No practice areas listed</span>
          )}
        </div>

        {entry.bio ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">{entry.bio}</p>
        ) : null}

        <div className="mt-auto flex gap-2 pt-1">
          <Button variant="outline" size="sm" className="flex-1" onClick={onOpen}>
            View profile
          </Button>
          <Button size="sm" className="flex-1" onClick={onRequest}>
            Request help
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function FindLawyerPage() {
  const navigate = useNavigate()
  const [searchInput, setSearchInput] = useState("")
  const [q, setQ] = useState("")
  const [category, setCategory] = useState("all")
  const [location, setLocation] = useState("")
  const [minExperience, setMinExperience] = useState("any")
  const [mode, setMode] = useState("all")
  const [verification, setVerification] = useState("any")
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<LawyerDirectoryEntry | null>(null)

  const loader = useCallback(
    () =>
      listLawyers({
        q,
        category,
        location,
        min_experience: minExperience === "any" ? undefined : Number(minExperience),
        consultation_mode: mode,
        verified_only: verification === "verified",
        limit: PAGE_SIZE,
        offset,
      }),
    [q, category, location, minExperience, mode, verification, offset],
  )
  const { state, refresh } = useAsync(loader)

  const items = state.data?.items ?? []
  const total = state.data?.total ?? 0
  const loading = state.phase === "loading" || state.phase === "idle"

  function requestFor(entry: LawyerDirectoryEntry) {
    const practice = entry.practice_areas[0]
    const params = new URLSearchParams()
    if (practice) params.set("category", practice)
    params.set("lawyer", String(entry.user_id))
    navigate(`/dashboard/post-case?${params.toString()}`)
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Find a lawyer</h1>
        <p className="text-sm text-muted-foreground">
          Browse legal professionals by practice area, location, experience and consultation
          preference, then post your matter for them to pick up.
        </p>
      </div>

      <Card>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <form
            className="flex flex-col gap-1.5"
            onSubmit={(event) => {
              event.preventDefault()
              setOffset(0)
              setQ(searchInput.trim())
            }}
          >
            <Label htmlFor="lawyer-search">Search</Label>
            <div className="flex gap-2">
              <Input
                id="lawyer-search"
                placeholder="Name, practice, language"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
              />
              <Button type="submit" variant="outline" size="icon" aria-label="Search lawyers">
                <Search className="size-4" aria-hidden="true" />
              </Button>
            </div>
          </form>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lawyer-category">Practice area</Label>
            <Select
              id="lawyer-category"
              value={category}
              onChange={(event) => {
                setOffset(0)
                setCategory(event.target.value)
              }}
            >
              {CASE_CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lawyer-location">Location</Label>
            <Input
              id="lawyer-location"
              placeholder="City or jurisdiction"
              value={location}
              onChange={(event) => {
                setOffset(0)
                setLocation(event.target.value)
              }}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lawyer-experience">Experience</Label>
            <Select
              id="lawyer-experience"
              value={minExperience}
              onChange={(event) => {
                setOffset(0)
                setMinExperience(event.target.value)
              }}
            >
              {EXPERIENCE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lawyer-mode">Consultation</Label>
            <Select
              id="lawyer-mode"
              value={mode}
              onChange={(event) => {
                setOffset(0)
                setMode(event.target.value)
              }}
            >
              {CONSULTATION_MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lawyer-verification">Verification</Label>
            <Select
              id="lawyer-verification"
              value={verification}
              onChange={(event) => {
                setOffset(0)
                setVerification(event.target.value)
              }}
            >
              <option value="any">Any status</option>
              <option value="verified">Verified only</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load lawyers"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={Scale}
          title="No lawyers match your filters"
          description="Try widening your search. New legal professionals appear here as they complete their profiles."
        />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {items.map((entry) => (
              <LawyerCard
                key={entry.user_id}
                entry={entry}
                onOpen={() => setSelected(entry)}
                onRequest={() => requestFor(entry)}
              />
            ))}
          </div>

          {total > PAGE_SIZE ? (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          {selected ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {selected.full_name ?? "Unnamed lawyer"}
                  <VerifiedBadge status={selected.verification_status} />
                </DialogTitle>
                <DialogDescription>
                  {selected.location ?? selected.jurisdiction ?? "Location not stated"} ·{" "}
                  {experienceLabel(selected.years_experience)}
                </DialogDescription>
              </DialogHeader>

              <div className="flex flex-col gap-4 text-sm">
                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-muted-foreground">Practice areas</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.practice_areas.length > 0 ? (
                      selected.practice_areas.map((area) => (
                        <Badge key={area} variant="secondary">
                          {caseCategoryLabel(area)}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-muted-foreground">Not listed</span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-muted-foreground">Languages</span>
                  <span>{selected.languages.join(", ") || "Not listed"}</span>
                </div>

                <div className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-muted-foreground">
                    Consultation formats
                  </span>
                  <span>
                    {selected.consultation_modes.map(consultationModeLabel).join(", ") ||
                      "Not listed"}
                  </span>
                </div>

                {selected.fee_structure ? (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-muted-foreground">Fee structure</span>
                    <span>{selected.fee_structure}</span>
                  </div>
                ) : null}

                {selected.availability ? (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-muted-foreground">Availability</span>
                    <span>{selected.availability}</span>
                  </div>
                ) : null}

                {selected.bio ? (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs font-medium text-muted-foreground">About</span>
                    <p className="whitespace-pre-line">{selected.bio}</p>
                  </div>
                ) : null}

                {selected.verification_status !== "VERIFIED" ? (
                  <p className="rounded-lg border border-border p-3 text-xs text-muted-foreground">
                    This profile has not been independently verified. Credentials are self-reported.
                  </p>
                ) : null}
              </div>

              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">Close</Button>
                </DialogClose>
                <Button onClick={() => requestFor(selected)}>Request legal assistance</Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
