import { riskLevelFromScore, RISK_META } from "@/lib/risk"

export function RiskScore({
  score,
  size = 132,
  thickness = 12,
  label = "Risk score",
}: {
  score: number
  size?: number
  thickness?: number
  label?: string
}) {
  const level = riskLevelFromScore(score)
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  const progress = Math.min(100, Math.max(0, score))
  const dash = (progress / 100) * circumference

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={thickness}
            className="stroke-muted"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={thickness}
            stroke={RISK_META[level].hex}
            strokeDasharray={`${dash} ${circumference - dash}`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-semibold tracking-tight">{score}</span>
          <span className="text-xs text-muted-foreground">/ 100</span>
        </div>
      </div>
      <div className="text-center">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs" style={{ color: RISK_META[level].hex }}>
          {RISK_META[level].label} risk
        </p>
      </div>
    </div>
  )
}
