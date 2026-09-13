// Single source of truth for colour tokens that can't go through Tailwind's
// class scanner (Recharts `fill`/`stroke` props, inline styles). Mirrors
// tailwind.config.js exactly -- change a hex in one place, update the other.
//
// Every badge, chart and status indicator in the app should import from
// here rather than re-declaring its own color map, so a status always
// renders the same colour no matter which screen it appears on.

export const CHART_COLORS = {
  navy: '#0b3355',
  blue: '#1d63a8',
  green: '#1b8a5a',
  amber: '#b7791f',
  red: '#c0392b',
  ink: '#16232e',
  muted: '#55636e',
  line: '#dce2e8',
}

// Risk-level colour + background pairs. Keys are upper-case to match the
// backend's risk_level values directly (LOW | MEDIUM | HIGH | CRITICAL).
export const RISK_TONE = {
  LOW: { color: '#1b8a5a', bg: '#e7f4ec', label: 'Low' },
  MEDIUM: { color: '#b7791f', bg: '#fbf0de', label: 'Medium' },
  HIGH: { color: '#b4552e', bg: '#fbe7df', label: 'High' },
  CRITICAL: { color: '#c0392b', bg: '#fadcd8', label: 'Critical' },
}

export const RISK_ORDER = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

// Accepts either 'HIGH' or 'High' (backend vs. already-title-cased) and
// always returns a tone object; unknown/missing values fall back to a
// neutral grey rather than guessing a severity.
export function riskTone(level) {
  if (!level) return { color: '#55636e', bg: '#eef1f3', label: 'Unknown' }
  const key = String(level).toUpperCase()
  return RISK_TONE[key] || { color: '#55636e', bg: '#eef1f3', label: String(level) }
}

export const STATUS_TONE = {
  Completed: { color: '#1b8a5a', bg: '#e7f4ec' },
  Ongoing: { color: '#2b6cb0', bg: '#e4eef9' },
  'In Progress': { color: '#2b6cb0', bg: '#e4eef9' },
  Sanctioned: { color: '#1d63a8', bg: '#e7eef6' },
  Recommended: { color: '#55636e', bg: '#eef1f3' },
  Delayed: { color: '#c0392b', bg: '#fadcd8' },
}

export function statusTone(status) {
  return STATUS_TONE[status] || { color: '#55636e', bg: '#eef1f3' }
}