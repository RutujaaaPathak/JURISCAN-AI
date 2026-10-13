import { cn } from "@/lib/utils"

export interface ChartDatum {
  label: string
  value: number
  color?: string
}

export function DonutChart({
  data,
  size = 168,
  thickness = 20,
  centerLabel,
  centerValue,
}: {
  data: ChartDatum[]
  size?: number
  thickness?: number
  centerLabel?: string
  centerValue?: string | number
}) {
  const total = data.reduce((sum, datum) => sum + datum.value, 0)
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label="Distribution chart">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={thickness}
          className="stroke-muted"
        />
        {total > 0
          ? data.map((datum) => {
              const length = (datum.value / total) * circumference
              const dash = `${length} ${circumference - length}`
              const element = (
                <circle
                  key={datum.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  strokeWidth={thickness}
                  stroke={datum.color ?? "var(--primary)"}
                  strokeDasharray={dash}
                  strokeDashoffset={-offset}
                  strokeLinecap="butt"
                />
              )
              offset += length
              return element
            })
          : null}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold tracking-tight">{centerValue ?? total}</span>
        {centerLabel ? <span className="text-xs text-muted-foreground">{centerLabel}</span> : null}
      </div>
    </div>
  )
}

export function BarChart({
  data,
  color = "var(--primary)",
  height = 160,
  valueSuffix = "",
}: {
  data: ChartDatum[]
  color?: string
  height?: number
  valueSuffix?: string
}) {
  const max = Math.max(1, ...data.map((datum) => datum.value))

  return (
    <div className="flex items-end gap-2" style={{ height }}>
      {data.map((datum) => {
        const pct = (datum.value / max) * 100
        return (
          <div key={datum.label} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-2">
            <span className="text-xs font-medium text-muted-foreground">
              {datum.value}
              {valueSuffix}
            </span>
            <div
              className="w-full rounded-t-md transition-all"
              style={{ height: `${pct}%`, backgroundColor: datum.color ?? color }}
              title={`${datum.label}: ${datum.value}${valueSuffix}`}
            />
            <span className="truncate text-[11px] text-muted-foreground">{datum.label}</span>
          </div>
        )
      })}
    </div>
  )
}

export function CategoryBars({
  data,
  max,
}: {
  data: { label: string; value: number; color?: string }[]
  max?: number
}) {
  const peak = max ?? Math.max(1, ...data.map((datum) => datum.value))
  return (
    <ul className="flex flex-col gap-3">
      {data.map((datum) => (
        <li key={datum.label} className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">{datum.label}</span>
            <span className="text-muted-foreground">{datum.value}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full")}
              style={{ width: `${(datum.value / peak) * 100}%`, backgroundColor: datum.color ?? "var(--primary)" }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
