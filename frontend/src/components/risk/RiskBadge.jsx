import React from 'react'
import { RiskBadge as SharedRiskBadge } from '../UI'

// Thin re-export so existing `import RiskBadge from '../components/risk/RiskBadge'`
// call sites keep working -- the actual implementation now lives in the
// shared UI kit (components/UI.jsx) so risk colour logic exists in
// exactly one place.
export default function RiskBadge({ risk }) {
  return <SharedRiskBadge risk={risk} />
}