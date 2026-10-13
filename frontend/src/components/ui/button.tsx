import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-xl border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-[#ebd080] via-[#e5c158] to-[#c99e3a] text-[#070a13] font-semibold hover:brightness-105 shadow-[0_2px_12px_rgba(229,193,88,0.22)] active:scale-[0.99]",
        outline:
          "border border-white/12 bg-white/[0.05] hover:bg-white/[0.1] text-foreground hover:text-foreground backdrop-blur-sm",
        secondary:
          "border border-white/8 bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost:
          "hover:bg-white/[0.08] hover:text-foreground",
        destructive:
          "bg-destructive/15 text-destructive border border-destructive/20 hover:bg-destructive/25",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 gap-2 px-4 rounded-xl text-sm",
        xs: "h-6 gap-1 rounded-lg px-2 text-xs",
        sm: "h-8 gap-1.5 rounded-lg px-3 text-xs font-medium",
        lg: "h-11 gap-2 px-5 rounded-xl text-sm font-semibold",
        icon: "size-9 rounded-xl",
        "icon-xs": "size-6 rounded-lg",
        "icon-sm": "size-8 rounded-lg",
        "icon-lg": "size-10 rounded-xl",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
