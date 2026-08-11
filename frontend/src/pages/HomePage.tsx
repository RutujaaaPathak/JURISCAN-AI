import { ShieldCheck } from "lucide-react"

import { Button } from "@/components/ui/button"

export function HomePage() {
  return (
    <section className="flex flex-1 items-center justify-center">
      <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-6 py-16 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          JurisScan-AI
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          AI-powered legal document auditing and contract analysis.
        </p>
        <div className="mt-8">
          <Button size="lg">Get Started</Button>
        </div>
        <div className="mt-12 flex flex-col items-center gap-2 rounded-lg border border-border bg-muted/50 px-6 py-4 sm:flex-row sm:gap-4">
          <span className="flex items-center gap-2 text-sm font-medium text-foreground">
            <ShieldCheck className="size-4 text-green-600" aria-hidden="true" />
            System Ready
          </span>
          <span className="hidden text-muted-foreground sm:block" aria-hidden="true">
            •
          </span>
          <span className="text-sm text-muted-foreground">
            Frontend foundation initialized
          </span>
        </div>
      </div>
    </section>
  )
}
