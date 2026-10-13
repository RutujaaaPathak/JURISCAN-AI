export type Tone = "default" | "success" | "warning" | "destructive"

/**
 * Semantic surface tints for icon chips and activity markers. Uses theme tokens
 * so the same class string reads correctly in both light and dark mode.
 */
export const TONE_SURFACE: Record<Tone, string> = {
  default: "bg-muted text-muted-foreground",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  destructive: "bg-destructive/12 text-destructive",
}
