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
      "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
    dot: "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]",
    bar: "bg-emerald-500",
    hex: "#10b981",
  },
  medium: {
    label: "Medium",
    order: 1,
    badge:
      "border-amber-500/25 bg-amber-500/10 text-amber-300",
    dot: "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.7)]",
    bar: "bg-amber-500",
    hex: "#f59e0b",
  },
  high: {
    label: "High",
    order: 2,
    badge:
      "border-orange-500/25 bg-orange-500/10 text-orange-300",
    dot: "bg-orange-400 shadow-[0_0_6px_rgba(251,146,60,0.7)]",
    bar: "bg-orange-500",
    hex: "#f97316",
  },
  critical: {
    label: "Critical",
    order: 3,
    badge:
      "border-rose-500/25 bg-rose-500/10 text-rose-300",
    dot: "bg-rose-400 shadow-[0_0_6px_rgba(251,113,133,0.7)]",
    bar: "bg-rose-500",
    hex: "#f43f5e",
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
