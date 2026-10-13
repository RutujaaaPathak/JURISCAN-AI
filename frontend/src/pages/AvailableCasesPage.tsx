import { Inbox, Search } from "lucide-react"
import { useCallback, useState } from "react"
import { Link } from "react-router-dom"

import { CaseTable } from "@/components/cases/CaseTable"
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/common/States"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select } from "@/components/ui/select"
import { useAsync } from "@/hooks/useAsync"
import { listCases } from "@/lib/cases"
import { CASE_CATEGORY_OPTIONS, CASE_SORT_OPTIONS, CASE_URGENCY_OPTIONS } from "@/lib/caseFilters"

const PAGE_SIZE = 10

export function AvailableCasesPage() {
  const [searchInput, setSearchInput] = useState("")
  const [q, setQ] = useState("")
  const [category, setCategory] = useState("all")
  const [urgency, setUrgency] = useState("ALL")
  const [sort, setSort] = useState("recent")
  const [offset, setOffset] = useState(0)

  const loader = useCallback(
    () => listCases({ q, category, urgency, sort, limit: PAGE_SIZE, offset }),
    [q, category, urgency, sort, offset],
  )
  const { state, refresh } = useAsync(loader)

  const items = state.data?.items ?? []
  const total = state.data?.total ?? 0
  const loading = state.phase === "loading" || state.phase === "idle"

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Available cases</h1>
        <p className="text-sm text-muted-foreground">
          Open matters posted by clients. Accept one to take it on, or request more information
          before deciding.
        </p>
      </div>

      <Card>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <form
            className="flex flex-col gap-1.5"
            onSubmit={(event) => {
              event.preventDefault()
              setOffset(0)
              setQ(searchInput.trim())
            }}
          >
            <Label htmlFor="case-search">Search</Label>
            <div className="flex gap-2">
              <Input
                id="case-search"
                placeholder="Title or summary"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
              />
              <Button type="submit" variant="outline" size="icon" aria-label="Search cases">
                <Search className="size-4" aria-hidden="true" />
              </Button>
            </div>
          </form>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="case-category">Category</Label>
            <Select
              id="case-category"
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
            <Label htmlFor="case-urgency">Urgency</Label>
            <Select
              id="case-urgency"
              value={urgency}
              onChange={(event) => {
                setOffset(0)
                setUrgency(event.target.value)
              }}
            >
              {CASE_URGENCY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="case-sort">Sort</Label>
            <Select
              id="case-sort"
              value={sort}
              onChange={(event) => {
                setOffset(0)
                setSort(event.target.value)
              }}
            >
              {CASE_SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : state.phase === "error" ? (
        <ErrorState
          title="Could not load cases"
          description={state.error ?? undefined}
          onRetry={() => void refresh()}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <CaseTable
            cases={items}
            empty={
              <EmptyState
                icon={Inbox}
                title="No matching cases"
                description="Try widening your filters, or check back when new matters are posted."
              />
            }
            renderAction={(item) => (
              <Button variant="ghost" size="sm" asChild>
                <Link to={`/dashboard/cases/${item.id}`}>Review</Link>
              </Button>
            )}
          />

          {total > 0 ? (
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
    </div>
  )
}
