import { cva, type VariantProps } from "class-variance-authority"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "flex w-full items-start gap-3 rounded-xl border p-4 text-sm backdrop-blur-sm",
  {
    variants: {
      variant: {
        default: "border-white/10 bg-card/80 text-card-foreground",
        info: "border-info/25 bg-info/10 text-info",
        success: "border-success/25 bg-success/10 text-success",
        warning: "border-warning/25 bg-warning/10 text-warning",
        destructive: "border-destructive/30 bg-destructive/10 text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

function Alert({
  className,
  variant,
  ...props
}: ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div role="alert" data-slot="alert" className={cn(alertVariants({ variant }), className)} {...props} />
  )
}

function AlertTitle({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="alert-title" className={cn("font-medium", className)} {...props} />
}

function AlertDescription({ className, ...props }: ComponentProps<"div">) {
  return (
    <div data-slot="alert-description" className={cn("text-sm opacity-90", className)} {...props} />
  )
}

export { Alert, AlertDescription, AlertTitle }