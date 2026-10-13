export type RiskLevel = "low" | "medium" | "high" | "critical"

export interface RiskMeta {
  label: string
  order: number
  badge: string
  dot: string
  bar: string
  hex: string
}

export const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "critical"]

export const RISK_META: Record<RiskLevel, RiskMeta> = {
  low: {
    label: "Low",
    order: 0,
    badge:
      "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
    dot: "bg-emerald-500",
    bar: "bg-emerald-500",
    hex: "#10b981",
  },
  medium: {
    label: "Medium",
    order: 1,
    badge:
      "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300",
    dot: "bg-amber-500",
    bar: "bg-amber-500",
    hex: "#f59e0b",
  },
  high: {
    label: "High",
    order: 2,
    badge:
      "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900 dark:bg-orange-950 dark:text-orange-300",
    dot: "bg-orange-500",
    bar: "bg-orange-500",
    hex: "#f97316",
  },
  critical: {
    label: "Critical",
    order: 3,
    badge:
      "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300",
    dot: "bg-red-600",
    bar: "bg-red-600",
    hex: "#dc2626",
  },
}

export function riskLevelFromScore(score: number): RiskLevel {
  if (score >= 75) return "critical"
  if (score >= 50) return "high"
  if (score >= 25) return "medium"
  return "low"
}

export function toRiskLevel(value: string | null | undefined): RiskLevel | null {
  if (!value) return null
  const lowered = value.toLowerCase()
  if (lowered === "low" || lowered === "medium" || lowered === "high" || lowered === "critical") {
    return lowered
  }
  return null
}

export function riskLevelFromScoreOrNull(score: number | null | undefined): RiskLevel | null {
  if (score === null || score === undefined) return null
  return riskLevelFromScore(score)
}
