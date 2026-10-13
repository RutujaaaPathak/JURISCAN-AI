import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export function AuthLayout({
  title,
  description,
  children,
  footer,
  wide = false,
}: {
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  return (
    <div className="bg-hero relative flex flex-1 flex-col items-center justify-center px-4 py-14 sm:px-6 sm:py-20">
      <div
        className="bg-grid pointer-events-none absolute inset-0 opacity-30 [mask-image:radial-gradient(40rem_28rem_at_50%_0%,black,transparent)]"
        aria-hidden="true"
      />
      <div className={cn("relative w-full", wide ? "max-w-2xl" : "max-w-md")}>
        <div className="flex flex-col gap-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
          {description ? (
            <p className="text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        <div className="mt-8">{children}</div>
        {footer ? (
          <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div>
        ) : null}
      </div>
    </div>
  )
}
