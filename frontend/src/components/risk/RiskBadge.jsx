import React from 'react'
import { Badge } from '../UI'

export default function RiskBadge({ risk }) {
  const styles = { Critical: 'bg-red-100 text-red-800', High: 'bg-rose-50 text-rose-700', Medium: 'bg-amber-50 text-amber-700', Low: 'bg-emerald-50 text-emerald-700' }
  return <Badge className={styles[risk] || 'bg-slate-100 text-slate-600'}>{risk || 'Unknown'} risk</Badge>
}
