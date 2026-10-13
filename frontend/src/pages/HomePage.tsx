import {
  Building2,
  Database,
  FileSearch,
  FileText,
  Gavel,
  ScanLine,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { ConnectionStatus } from "@/components/layout/ConnectionStatus"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useRole } from "@/context/RoleContext"
import type { UserRole } from "@/lib/roles"

const features = [
  {
    icon: ScanLine,
    title: "Clause segmentation",
    description:
      "Split contracts into structured clauses ready for review. Extraction pipeline planned for a later phase.",
  },
  {
    icon: ShieldCheck,
    title: "Risk detection",
    description:
      "Surface risky language with severity, explanations and legal citations once the analysis model is trained.",
  },
  {
    icon: FileSearch,
    title: "Explained findings",
    description:
      "Every finding will include a human-readable explanation and a recommendation instead of a bare score.",
  },
  {
    icon: Database,
    title: "Auditable storage",
    description:
      "Documents, clauses, analyses and risk findings persist in PostgreSQL with a versioned schema.",
  },
]

const steps = [
  { icon: FileText, title: "Upload", text: "Bring a PDF, DOCX or TXT legal document." },
  { icon: ScanLine, title: "Analyse", text: "Extract clauses and detect risk with AI assistance." },
  { icon: ShieldCheck, title: "Act", text: "Review highlighted clauses and remediation guidance." },
]

export function HomePage() {
  const navigate = useNavigate()
  const { setRole } = useRole()

  const openDashboard = (role: UserRole) => {
    setRole(role)
    navigate("/dashboard")
  }

  return (
    <div className="flex flex-col">
      <section className="mx-auto flex w-full max-w-6xl flex-col items-center px-4 py-20 text-center sm:px-6 sm:py-28">
        <Badge variant="secondary" className="gap-1.5">
          <Sparkles className="size-3.5" aria-hidden="true" />
          AI-powered contract review
        </Badge>
        <h1 className="mt-6 max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">
          Audit legal documents with confidence
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
          JurisScan-AI turns dense contracts into structured clauses and reviewable risk findings —
          with explanations, severity and citations you can act on.
        </p>
        <div className="mt-8 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
          <Button
            variant="outline"
            size="lg"
            className="justify-center"
            onClick={() => openDashboard("individual")}
          >
            <User className="size-4" aria-hidden="true" />
            User Dashboard
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="justify-center"
            onClick={() => openDashboard("company")}
          >
            <Building2 className="size-4" aria-hidden="true" />
            Company Dashboard
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="justify-center"
            onClick={() => openDashboard("lawyer")}
          >
            <Gavel className="size-4" aria-hidden="true" />
            Lawyer Dashboard
          </Button>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Preview modes for the shared workspace — sign-in and role-based access are not implemented
          yet.
        </p>
        <div className="mt-6">
          <Button asChild variant="ghost" size="lg">
            <a href="#features">Explore features</a>
          </Button>
        </div>

        <div className="mt-10 flex flex-col items-center gap-2 rounded-lg border border-border bg-muted/40 px-5 py-4 sm:flex-row sm:gap-4">
          <span className="text-sm font-medium">Backend status</span>
          <ConnectionStatus />
        </div>
      </section>

      <section id="features" className="border-y border-border bg-muted/30">
        <div className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold tracking-tight">Built for legal review workflows</h2>
            <p className="mt-3 text-muted-foreground">
              The platform is being built in phases. Items below describe the target capability set.
            </p>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-2">
            {features.map((feature) => (
              <Card key={feature.title}>
                <CardHeader>
                  <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <feature.icon className="size-5" aria-hidden="true" />
                  </span>
                  <CardTitle className="mt-2">{feature.title}</CardTitle>
                  <CardDescription>{feature.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Badge variant="outline">Phase 4+</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight">How it works</h2>
          <p className="mt-3 text-muted-foreground">
            A three-step review loop, from raw document to remediation guidance.
          </p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-3">
          {steps.map((step, index) => (
            <Card key={step.title}>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
                    {index + 1}
                  </span>
                  <step.icon className="size-5 text-muted-foreground" aria-hidden="true" />
                </div>
                <CardTitle className="mt-2">{step.title}</CardTitle>
                <CardDescription>{step.text}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-primary text-primary-foreground">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-6 px-4 py-16 text-center sm:px-6">
          <h2 className="text-3xl font-semibold tracking-tight">Foundation is in place</h2>
          <p className="max-w-xl opacity-90">
            Frontend routing, backend API, PostgreSQL schema and migrations are ready. Document
            processing and the Legal-BERT analysis pipeline come next.
          </p>
          <Button asChild size="lg" variant="secondary">
            <Link to="/dashboard">Go to dashboard</Link>
          </Button>
        </div>
      </section>
    </div>
  )
}