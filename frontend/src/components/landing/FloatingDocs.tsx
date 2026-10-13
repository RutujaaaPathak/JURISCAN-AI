import type { CSSProperties } from "react"
import { cn } from "@/lib/utils"

export function CurledLegalDoc({
  className,
  style,
  variant = "top-right",
}: {
  className?: string
  style?: CSSProperties
  variant?: "top-right" | "bottom-left" | "top-left" | "distant"
}) {
  if (variant === "top-right") {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none select-none transition-transform will-change-transform",
          className,
        )}
        style={style}
      >
        <svg
          width="132"
          height="168"
          viewBox="0 0 132 168"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="drop-shadow-[0_18px_30px_rgba(0,0,0,0.65)]"
        >
          <defs>
            <linearGradient id="docGradTR" x1="0" y1="0" x2="132" y2="168" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#fdfbf7" stopOpacity="0.95" />
              <stop offset="55%" stopColor="#e2e8f0" stopOpacity="0.88" />
              <stop offset="100%" stopColor="#94a3b8" stopOpacity="0.75" />
            </linearGradient>
            <linearGradient id="curlGradTR" x1="96" y1="132" x2="132" y2="168" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#64748b" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#cbd5e1" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#f8fafc" stopOpacity="1" />
            </linearGradient>
            <filter id="curlShadowTR" x="78" y="114" width="60" height="60" filterUnits="userSpaceOnUse">
              <feDropShadow dx="-3" dy="-3" stdDeviation="4" floodColor="#050811" floodOpacity="0.5" />
            </filter>
          </defs>

          {/* Main Paper Body with cut-out curled corner */}
          <path
            d="M8 2 C28 0, 104 2, 124 6 C128 7, 130 9, 130 14 L130 132 C120 134, 106 142, 96 164 C94 167, 91 168, 86 167 C50 165, 20 166, 6 163 C2 162, 0 159, 0 154 L2 14 C2 8, 4 3, 8 2 Z"
            fill="url(#docGradTR)"
          />

          {/* Paper lines / clauses */}
          <rect x="18" y="24" width="36" height="3.5" rx="1.75" fill="#c5a868" opacity="0.8" />
          <rect x="18" y="38" width="86" height="2" rx="1" fill="#475569" opacity="0.35" />
          <rect x="18" y="47" width="94" height="2" rx="1" fill="#475569" opacity="0.3" />
          <rect x="18" y="56" width="76" height="2" rx="1" fill="#475569" opacity="0.3" />
          <rect x="18" y="65" width="88" height="2" rx="1" fill="#475569" opacity="0.25" />

          <rect x="18" y="80" width="44" height="2.5" rx="1.25" fill="#c5a868" opacity="0.6" />
          <rect x="18" y="91" width="90" height="2" rx="1" fill="#475569" opacity="0.3" />
          <rect x="18" y="100" width="82" height="2" rx="1" fill="#475569" opacity="0.25" />
          <rect x="18" y="109" width="70" height="2" rx="1" fill="#475569" opacity="0.25" />
          <rect x="18" y="118" width="60" height="2" rx="1" fill="#475569" opacity="0.2" />

          {/* Curled flap overlay with 3D shadow */}
          <path
            d="M130 132 C116 135, 106 145, 96 164 C104 150, 116 142, 130 132 Z"
            fill="#090e19"
            opacity="0.4"
          />
          <path
            d="M130 132 C120 144, 110 154, 96 164 C108 162, 122 152, 130 132 Z"
            fill="url(#curlGradTR)"
            stroke="#ffffff"
            strokeWidth="0.75"
            strokeOpacity="0.6"
            filter="url(#curlShadowTR)"
          />
        </svg>
      </div>
    )
  }

  if (variant === "bottom-left") {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none select-none transition-transform will-change-transform",
          className,
        )}
        style={style}
      >
        <svg
          width="160"
          height="200"
          viewBox="0 0 160 200"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="drop-shadow-[0_24px_38px_rgba(0,0,0,0.7)]"
        >
          <defs>
            <linearGradient id="docGradBL" x1="0" y1="0" x2="160" y2="200" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
              <stop offset="60%" stopColor="#cbd5e1" stopOpacity="0.82" />
              <stop offset="100%" stopColor="#64748b" stopOpacity="0.7" />
            </linearGradient>
            <linearGradient id="curlGradBL" x1="0" y1="160" x2="40" y2="200" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#94a3b8" />
              <stop offset="70%" stopColor="#e2e8f0" />
              <stop offset="100%" stopColor="#ffffff" />
            </linearGradient>
          </defs>

          {/* Curled lower legal sheet */}
          <path
            d="M14 6 C40 2, 130 0, 152 4 C157 5, 159 8, 158 14 L154 186 C153 192, 150 196, 144 196 C110 195, 60 196, 42 195 C34 175, 20 162, 0 158 L6 14 C7 8, 9 5, 14 6 Z"
            fill="url(#docGradBL)"
          />

          {/* Lined clauses */}
          <rect x="24" y="28" width="40" height="4" rx="2" fill="#c5a868" opacity="0.85" />
          <rect x="24" y="44" width="108" height="2.5" rx="1.25" fill="#334155" opacity="0.4" />
          <rect x="24" y="55" width="116" height="2.5" rx="1.25" fill="#334155" opacity="0.35" />
          <rect x="24" y="66" width="98" height="2.5" rx="1.25" fill="#334155" opacity="0.35" />
          <rect x="24" y="77" width="104" height="2.5" rx="1.25" fill="#334155" opacity="0.3" />
          <rect x="24" y="88" width="86" height="2.5" rx="1.25" fill="#334155" opacity="0.3" />

          <rect x="24" y="104" width="46" height="3" rx="1.5" fill="#c5a868" opacity="0.7" />
          <rect x="24" y="117" width="110" height="2.5" rx="1.25" fill="#334155" opacity="0.35" />
          <rect x="24" y="128" width="94" height="2.5" rx="1.25" fill="#334155" opacity="0.3" />
          <rect x="24" y="139" width="76" height="2.5" rx="1.25" fill="#334155" opacity="0.25" />
          <rect x="24" y="150" width="62" height="2.5" rx="1.25" fill="#334155" opacity="0.2" />

          {/* Bottom curl corner */}
          <path
            d="M0 158 C18 162, 32 175, 42 195 C28 188, 14 176, 0 158 Z"
            fill="url(#curlGradBL)"
            stroke="#ffffff"
            strokeWidth="0.75"
            strokeOpacity="0.5"
          />
        </svg>
      </div>
    )
  }

  if (variant === "top-left") {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "pointer-events-none select-none transition-transform will-change-transform opacity-50",
          className,
        )}
        style={style}
      >
        <svg
          width="90"
          height="115"
          viewBox="0 0 90 115"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="drop-shadow-[0_12px_24px_rgba(0,0,0,0.55)]"
        >
          <path
            d="M6 3 C25 1, 70 2, 84 5 C88 6, 89 8, 89 12 L87 106 C87 110, 84 112, 80 112 L10 111 C6 111, 4 109, 3 105 L1 10 C1 6, 3 3, 6 3 Z"
            fill="#e2e8f0"
            fillOpacity="0.7"
          />
          <rect x="12" y="16" width="24" height="2.5" rx="1.25" fill="#c5a868" opacity="0.7" />
          <rect x="12" y="26" width="62" height="1.5" rx="0.75" fill="#475569" opacity="0.4" />
          <rect x="12" y="33" width="66" height="1.5" rx="0.75" fill="#475569" opacity="0.35" />
          <rect x="12" y="40" width="54" height="1.5" rx="0.75" fill="#475569" opacity="0.3" />
          <rect x="12" y="52" width="58" height="1.5" rx="0.75" fill="#475569" opacity="0.3" />
          <rect x="12" y="59" width="48" height="1.5" rx="0.75" fill="#475569" opacity="0.25" />
        </svg>
      </div>
    )
  }

  // distant background
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none select-none transition-transform will-change-transform opacity-30 blur-[1px]",
        className,
      )}
      style={style}
    >
      <svg
        width="65"
        height="85"
        viewBox="0 0 65 85"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="drop-shadow-md"
      >
        <rect width="65" height="85" rx="4" fill="#cbd5e1" fillOpacity="0.5" />
        <rect x="8" y="10" width="18" height="2" rx="1" fill="#c5a868" opacity="0.6" />
        <rect x="8" y="18" width="46" height="1.5" rx="0.75" fill="#64748b" opacity="0.3" />
        <rect x="8" y="24" width="42" height="1.5" rx="0.75" fill="#64748b" opacity="0.3" />
        <rect x="8" y="30" width="36" height="1.5" rx="0.75" fill="#64748b" opacity="0.25" />
      </svg>
    </div>
  )
}

export function DiamondSparkle({
  className,
  style,
}: {
  className?: string
  style?: CSSProperties
}) {
  return (
    <div
      aria-hidden="true"
      className={cn("pointer-events-none select-none", className)}
      style={style}
    >
      <svg
        width="44"
        height="44"
        viewBox="0 0 44 44"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="drop-shadow-[0_0_16px_rgba(255,255,255,0.7)]"
      >
        <defs>
          <linearGradient id="diamondGrad" x1="0" y1="0" x2="44" y2="44" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="45%" stopColor="#f1f5f9" />
            <stop offset="100%" stopColor="#94a3b8" />
          </linearGradient>
        </defs>
        <path
          d="M22 0 C22 12.15 31.85 22 44 22 C31.85 22 22 31.85 22 44 C22 31.85 12.15 22 0 22 C12.15 22 22 12.15 22 0 Z"
          fill="url(#diamondGrad)"
        />
      </svg>
    </div>
  )
}
