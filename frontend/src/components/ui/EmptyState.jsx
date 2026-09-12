import React from 'react'

export default function EmptyState({ text = 'No data available.' }) {
  return <div className="py-12 text-center text-slate-500 text-sm">{text}</div>
}
