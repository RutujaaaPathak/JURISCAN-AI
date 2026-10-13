import { Building2, ChevronRight, Gavel, User } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { AuthLayout } from "@/components/auth/AuthLayout"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ROLE_META } from "@/lib/roles"
import type { UserRole } from "@/lib/roles"

interface SignUpOption {
  role: Exclude<UserRole, "admin">
  icon: LucideIcon
  points: string[]
}

const OPTIONS: SignUpOption[] = [
  {
    role: "individual",
    icon: User,
    points: [
      "Review personal contracts and agreements",
      "Post legal matters and find a lawyer",
      "Track your own case conversations",
    ],
  },
  {
    role: "company",
    icon: Building2,
    points: [
      "Shared workspace for in-house teams",
      "Organise company contracts and reviews",
      "Compliance-oriented document storage",
    ],
  },
  {
    role: "lawyer",
    icon: Gavel,
    points: [
      "Receive and manage client cases",
      "Publish a professional profile",
      "Message clients and propose consultations",
    ],
  },
]

export function SignUpPage() {
  const navigate = useNavigate()

  return (
    <AuthLayout
      wide
      title="Create your account"
      description="Choose the workspace that fits how you work. Your role is set from this choice and enforced by the backend."
      footer={
        <>
          Already have an account?{" "}
          <Link className="font-medium text-primary hover:underline" to="/login">
            Sign in
          </Link>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-3">
        {OPTIONS.map((option) => {
          const Icon = option.icon
          return (
            <Card key={option.role} className="flex flex-col">
              <CardContent className="flex flex-1 flex-col gap-4 pt-6">
                <span className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <div className="flex flex-col gap-1">
                  <p className="font-semibold">{ROLE_META[option.role].label}</p>
                  <p className="text-sm text-muted-foreground">
                    {ROLE_META[option.role].description}
                  </p>
                </div>
                <ul className="flex flex-col gap-1.5 text-sm text-muted-foreground">
                  {option.points.map((point) => (
                    <li key={point} className="flex items-start gap-2">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary/60" aria-hidden="true" />
                      {point}
                    </li>
                  ))}
                </ul>
                <Button
                  className="mt-auto justify-between"
                  onClick={() => navigate(`/signup/${option.role}`)}
                >
                  Continue
                  <ChevronRight className="size-4" aria-hidden="true" />
                </Button>
              </CardContent>
            </Card>
          )
        })}
      </div>
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Administrator accounts are provisioned by the platform and cannot be created through public
        sign-up.
      </p>
    </AuthLayout>
  )
}
