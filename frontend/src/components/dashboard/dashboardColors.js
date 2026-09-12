// Institutional colour tokens for Dashboard-only chart/legend accents,
// taken from the approved MPLADS AI Shield visual reference.
//
// These are plain hex values (not Tailwind classes) because they're
// consumed by Recharts `fill` props and a handful of inline styles,
// neither of which go through Tailwind's class scanner. General page
// chrome (cards, buttons, headings) keeps using the existing Tailwind
// tokens from tailwind.config.js (navy/ink/muted/panel/line) so the
// Dashboard stays visually consistent with the rest of the F1/F2 shell --
// this file only fills the small gap of chart-specific accent colors
// that don't already have a Tailwind utility.

export const CHART_COLORS = {
  navy: '#0b3355',
  blue: '#1d63a8',
  green: '#1b8a5a',
  amber: '#b7791f',
  red: '#c0392b',
}

// Severity ramp for risk_level_counts charts/legends. HIGH sits between
// amber and red so it reads as visually distinct from CRITICAL.
export const RISK_COLORS = {
  LOW: '#1b8a5a',
  MEDIUM: '#b7791f',
  HIGH: '#b4552e',
  CRITICAL: '#c0392b',
}

export const RISK_ORDER = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

export const riskLabel = key => key.charAt(0) + key.slice(1).toLowerCase()
