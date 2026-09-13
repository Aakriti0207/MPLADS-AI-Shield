// Re-exports from the app-wide theme (src/lib/theme.js), which is now the
// single source of truth for colour tokens. Kept as a thin shim so
// existing Dashboard imports don't all need to change import paths.
import { CHART_COLORS, RISK_TONE, RISK_ORDER, riskTone } from '../../lib/theme'

export { CHART_COLORS, RISK_ORDER }

export const RISK_COLORS = Object.fromEntries(
  Object.entries(RISK_TONE).map(([key, tone]) => [key, tone.color])
)

export const riskLabel = key => riskTone(key).label