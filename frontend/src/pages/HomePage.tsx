import {
  Building2,
  ClipboardList,
  Database,
  FileSearch,
  FileText,
  ScanLine,
  ShieldCheck,
  Users,
} from "lucide-react"
import type { CSSProperties } from "react"
import { Link } from "react-router-dom"

import { SeverityBadge } from "@/components/analysis/RiskBadges"
import { ConnectionStatus } from "@/components/layout/ConnectionStatus"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { CurledLegalDoc, DiamondSparkle } from "@/components/landing/FloatingDocs"
import { useAuth } from "@/lib/auth"
import { dashboardPathForRole } from "@/lib/roles"

const features = [
  {
    icon: ScanLine,
    title: "Clause extraction",
    description:
      "Upload a PDF, DOCX or TXT file and JurisScan-AI splits it into numbered clauses so every part of the document is reviewable.",
  },
  {
    icon: ShieldCheck,
    title: "Explainable risk findings",
    description:
      "A transparent, rule-based engine flags risky language and returns a severity, a plain-language explanation and a suggested action for each finding.",
  },
  {
    icon: FileSearch,
    title: "Searchable text and citations",
    description:
      "Read the extracted document text, jump to the clause behind any finding, and see the references used to justify it.",
  },
  {
    icon: Database,
    title: "Persistent, auditable records",
    description:
      "Documents, clauses, findings and the activity around them are stored in the database so your review trail is preserved.",
  },
]

const steps = [
  { icon: FileText, title: "Upload", text: "Add a PDF, DOCX or TXT legal document to your workspace." },
  { icon: ScanLine, title: "Analyze", text: "Run the rule-based review to extract clauses and detect risk." },
  { icon: ShieldCheck, title: "Act", text: "Work through each finding and its recommended remediation." },
]

const audiences = [
  {
    icon: ClipboardList,
    title: "Individuals",
    text: "Review an agreement before you sign it and see the clauses that carry the most risk.",
  },
  {
    icon: Building2,
    title: "Companies",
    text: "Keep contract reviews and their findings in one place across your organization's documents.",
  },
  {
    icon: Users,
    title: "Lawyers and legal teams",
    text: "Triage documents quickly, then post and manage cases with clients inside a shared workspace.",
  },
]

const doesList = [
  "Extracts and numbers clauses from supported documents.",
  "Applies transparent, rule-based checks and reports findings.",
  "Explains each finding with a severity, reason and suggested action.",
  "Stores documents, findings and case activity in your workspace.",
]

const doesNotList = [
  "Provide legal advice, or create a lawyer-client relationship.",
  "Guarantee that every issue in a document is found.",
  "Replace review by a qualified lawyer.",
  "Make decisions for you without human review.",
]

function HeroBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* Top ambient spotlight glow radiating downward */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/4 w-[56rem] h-[34rem] rounded-full bg-[radial-gradient(ellipse_at_center,rgba(245,225,160,0.24)_0%,rgba(229,193,88,0.09)_42%,transparent_72%)] blur-2xl -z-10" />

      {/* Floating Curled Documents matching reference layout */}
      <CurledLegalDoc
        variant="top-left"
        className="animate-float absolute top-16 left-[14%] hidden md:block"
        style={{ "--tilt": "-15deg", animationDelay: "0.4s" } as CSSProperties}
      />
      <CurledLegalDoc
        variant="top-right"
        className="animate-float absolute top-20 right-[15%] hidden md:block"
        style={{ "--tilt": "18deg", animationDelay: "0.9s" } as CSSProperties}
      />
      <CurledLegalDoc
        variant="distant"
        className="animate-drift absolute top-14 right-[30%] hidden xl:block"
        style={{ "--tilt": "8deg", animationDelay: "1.8s" } as CSSProperties}
      />
      <CurledLegalDoc
        variant="bottom-left"
        className="animate-drift absolute bottom-24 left-[3%] hidden lg:block"
        style={{ "--tilt": "-24deg", animationDelay: "1.4s" } as CSSProperties}
      />

      {/* Diamond 4-point sparkle star in bottom right of hero */}
      <DiamondSparkle
        className="animate-pulse absolute bottom-20 right-[7%] hidden lg:block"
        style={{ animationDuration: "4s" }}
      />
    </div>
  )
}

export function HomePage() {
  const { user, status } = useAuth()
  const authenticated = status === "authenticated" && user !== null
  const primaryHref = authenticated ? dashboardPathForRole(user.role) : "/signup"

  return (
    <div className="flex flex-col bg-background text-foreground">
      <section className="bg-hero relative isolate overflow-hidden border-b border-white/[0.07] pt-14 pb-28 sm:pt-20 sm:pb-36">
        <HeroBackdrop />
        <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-start px-4 sm:px-6">
          <span className="animate-rise text-xs font-semibold tracking-[0.2em] text-[#c5a868] uppercase">
            CONTRACT REVIEW, MADE LEGIBLE
          </span>
          <h1
            className="animate-rise text-balance mt-6 max-w-3xl text-4xl sm:text-6xl lg:text-[4.25rem] font-bold tracking-tight text-foreground leading-[1.08]"
            style={{ animationDelay: "60ms" }}
          >
            See exactly what<br />
            your contracts say,<br />
            and where the{" "}
            <span className="relative inline-block">
              risk is
              <span
                className="risk-lens left-[42%] top-1/2 -translate-x-1/2 -translate-y-1/2"
                aria-hidden="true"
              />
            </span>
          </h1>
          <p
            className="animate-rise mt-6 max-w-xl text-base sm:text-lg text-muted-foreground leading-relaxed"
            style={{ animationDelay: "140ms" }}
          >
            JurisScan-AI turns dense legal documents into structured clauses and explained
            risk findings. Every flag comes with a severity, a reason you can read, and a
            suggested next step, so you can act with confidence.
          </p>
          <div
            className="animate-rise mt-9 flex flex-wrap items-center gap-3.5"
            style={{ animationDelay: "220ms" }}
          >
            <div className="relative inline-flex group">
              <span className="gold-button-halo" aria-hidden="true" />
              <Button asChild size="lg" className="btn-gold-primary h-11 px-6 text-sm font-semibold">
                <Link to={primaryHref}>{authenticated ? "Go to dashboard" : "Get started"}</Link>
              </Button>
            </div>
            <Button asChild variant="outline" size="lg" className="btn-dark-secondary h-11 px-5 text-sm font-medium">
              <Link to="/login">Log in</Link>
            </Button>
          </div>

          <div
            className="animate-rise mt-10 inline-flex items-center gap-3 rounded-xl border border-white/10 bg-[#090e1b]/80 px-4 py-2 shadow-sm backdrop-blur-md"
            style={{ animationDelay: "300ms" }}
          >
            <span className="text-sm text-muted-foreground">Service status</span>
            <ConnectionStatus />
          </div>
        </div>
      </section>

      <section id="features" className="relative -mt-10 z-20 mx-auto w-full max-w-6xl px-4 sm:px-6">
        <div className="rounded-3xl border border-white/10 bg-[#080d1a]/90 p-8 sm:p-12 backdrop-blur-xl shadow-2xl">
          <div className="max-w-2xl">
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-foreground">
              What JurisScan-AI does today
            </h2>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Everything below is available now in your workspace. The analysis is transparent and
              rule-based, so you can always see why a clause was flagged.
            </p>
          </div>
          <div className="mt-10 grid gap-5 sm:grid-cols-2">
            {features.map((feature) => (
              <Card key={feature.title} className="surface-panel rounded-2xl border border-white/8 hover:border-amber-400/20 transition-colors">
                <CardHeader>
                  <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                    <feature.icon className="size-5" aria-hidden="true" />
                  </span>
                  <CardTitle className="mt-3 text-foreground font-semibold">{feature.title}</CardTitle>
                  <CardDescription className="text-muted-foreground leading-relaxed">{feature.description}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-white/[0.07] py-20 sm:py-24">
        <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <span className="text-xs font-semibold tracking-[0.2em] text-[#c5a868] uppercase">
              Product preview
            </span>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-foreground">
              A report you can actually read
            </h2>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Findings are grouped, rated by severity and tied back to the exact clause they came
              from.
            </p>
          </div>

          <div className="mt-12 grid gap-6 lg:grid-cols-5">
            <Card className="surface-panel rounded-2xl border border-white/[0.08] lg:col-span-3">
              <CardHeader className="border-b border-white/[0.06] pb-4">
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="text-base text-foreground font-semibold">Master Services Agreement</CardTitle>
                  <Badge variant="outline" className="border-white/10 bg-white/5 text-muted-foreground">Illustrative example</Badge>
                </div>
                <CardDescription className="text-muted-foreground">Extracted clause with the flagged span highlighted</CardDescription>
              </CardHeader>
              <div className="p-5">
                <p className="text-xs font-medium tracking-wide text-[#c5a868] uppercase">
                  Clause 11.2 · Indemnity
                </p>
                <p className="mt-3 text-sm leading-relaxed text-foreground/90">
                  The Supplier shall indemnify, defend and hold harmless the Customer and its
                  affiliates{" "}
                  <mark className="rounded-sm bg-primary/25 px-1.5 py-0.5 text-foreground font-medium">
                    against any and all losses, claims, damages and expenses of whatsoever nature,
                    whether or not foreseeable
                  </mark>
                  , without a monetary cap.
                </p>
                <div className="mt-5 rounded-xl border border-white/[0.08] bg-[#070b16]/70 p-4">
                  <div className="flex items-center gap-2">
                    <SeverityBadge level="high" />
                    <span className="text-xs text-muted-foreground">Indemnity</span>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                    Uncapped, unrestricted indemnity favouring the counterparty. No cap, no
                    exclusion for consequential loss and no carve-out for the supplier's own
                    negligence.
                  </p>
                </div>
              </div>
            </Card>

            <Card className="surface-panel rounded-2xl border border-white/[0.08] lg:col-span-2">
              <CardHeader className="border-b border-white/[0.06] pb-4">
                <CardTitle className="text-base text-foreground font-semibold">Risk findings</CardTitle>
                <CardDescription className="text-muted-foreground">Severity, category and reason</CardDescription>
              </CardHeader>
              <ul className="divide-y divide-white/[0.06]">
                {[
                  { level: "critical" as const, label: "Indemnity", ref: "Clause 11.2" },
                  { level: "high" as const, label: "Payment terms", ref: "Clause 6.2" },
                  { level: "medium" as const, label: "Data protection", ref: "Clause 15.1" },
                  { level: "low" as const, label: "Confidentiality", ref: "Clause 12.3" },
                ].map((finding) => (
                  <li key={finding.ref} className="flex items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-white/[0.02]">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{finding.label}</p>
                      <p className="truncate text-xs text-muted-foreground">{finding.ref}</p>
                    </div>
                    <SeverityBadge level={finding.level} />
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="border-b border-white/[0.07] py-20 sm:py-24">
        <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <span className="text-xs font-semibold tracking-[0.2em] text-[#c5a868] uppercase">
              Workflow
            </span>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-foreground">How it works</h2>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              A three-step review loop, from raw document to remediation guidance.
            </p>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-3">
            {steps.map((step, index) => (
              <Card key={step.title} className="surface-panel rounded-2xl border border-white/[0.08]">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-r from-[#ebd080] to-[#c99e3a] text-sm font-bold text-[#070a13]">
                      {index + 1}
                    </span>
                    <step.icon className="size-5 text-muted-foreground" aria-hidden="true" />
                  </div>
                  <CardTitle className="mt-3 text-foreground font-semibold">{step.title}</CardTitle>
                  <CardDescription className="text-muted-foreground leading-relaxed">{step.text}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-white/[0.07] py-20 sm:py-24">
        <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <span className="text-xs font-semibold tracking-[0.2em] text-[#c5a868] uppercase">
              Scope
            </span>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-foreground">
              Capabilities and limits
            </h2>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              We would rather be clear about both. Here is exactly what the tool offers and what it
              does not.
            </p>
          </div>
          <div className="mt-12 grid gap-5 lg:grid-cols-2">
            <Card className="surface-panel rounded-2xl border border-white/[0.08]">
              <CardHeader className="pb-3">
                <CardTitle className="text-base text-foreground font-semibold">What it does</CardTitle>
              </CardHeader>
              <ul className="flex flex-col gap-3 px-5 pb-5">
                {doesList.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="surface-panel rounded-2xl border border-white/[0.08]">
              <CardHeader className="pb-3">
                <CardTitle className="text-base text-foreground font-semibold">What it does not do</CardTitle>
              </CardHeader>
              <ul className="flex flex-col gap-3 px-5 pb-5">
                {doesNotList.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      </section>

      <section className="border-b border-white/[0.07] py-20 sm:py-24">
        <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <span className="text-xs font-semibold tracking-[0.2em] text-[#c5a868] uppercase">
              Workspaces
            </span>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-foreground">Built around your role</h2>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Each account gets a workspace shaped to how it reviews and manages documents.
            </p>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-3">
            {audiences.map((audience) => (
              <Card key={audience.title} className="surface-panel rounded-2xl border border-white/[0.08]">
                <CardHeader>
                  <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                    <audience.icon className="size-5" aria-hidden="true" />
                  </span>
                  <CardTitle className="mt-3 text-foreground font-semibold">{audience.title}</CardTitle>
                  <CardDescription className="text-muted-foreground leading-relaxed">{audience.text}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden border-b border-white/[0.07] bg-hero py-20 sm:py-24">
        <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-start gap-6 px-4 sm:px-6">
          <span className="text-xs font-semibold tracking-[0.2em] text-[#c5a868] uppercase">
            Start reviewing
          </span>
          <h2 className="text-balance max-w-2xl text-3xl sm:text-4xl font-semibold tracking-tight text-foreground">
            Start reviewing in minutes
          </h2>
          <p className="max-w-xl text-muted-foreground leading-relaxed">
            Create an account, upload a document, and see your first explained risk findings.
          </p>
          <div className="relative inline-flex group">
            <span className="gold-button-halo" aria-hidden="true" />
            <Button asChild size="lg" className="btn-gold-primary h-11 px-6 text-sm font-semibold">
              <Link to={primaryHref}>{authenticated ? "Go to dashboard" : "Create your account"}</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
