import { Check, Monitor, Moon, Sun } from "lucide-react"
import { DropdownMenu } from "radix-ui"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useTheme } from "@/lib/theme"
import type { Theme } from "@/lib/theme"

const OPTIONS: { value: Theme; label: string; icon: LucideIcon }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
]

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const Icon = resolvedTheme === "dark" ? Moon : Sun

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button
          variant="outline"
          size="icon"
          className={cn("text-muted-foreground hover:text-foreground", className)}
          aria-label={`Theme preference: ${theme}. Open theme menu.`}
          title="Change theme"
        >
          <Icon className="size-4" aria-hidden="true" />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 min-w-40 rounded-xl border border-border bg-popover p-1 text-popover-foreground shadow-lg outline-none"
        >
          <DropdownMenu.Label className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
            Appearance
          </DropdownMenu.Label>
          {OPTIONS.map((option) => {
            const OptionIcon = option.icon
            const active = theme === option.value
            return (
              <DropdownMenu.Item
                key={option.value}
                onSelect={() => setTheme(option.value)}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none select-none",
                  "data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground",
                )}
              >
                <OptionIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                <span className="flex-1">{option.label}</span>
                {active ? (
                  <Check className="size-4 text-primary" aria-hidden="true" />
                ) : null}
              </DropdownMenu.Item>
            )
          })}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
