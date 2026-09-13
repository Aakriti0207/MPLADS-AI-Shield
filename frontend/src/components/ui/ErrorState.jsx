import React from 'react'
import { AlertTriangle } from 'lucide-react'

export default function ErrorState({ title = 'Could not load data', message, onRetry }) {
  return (
    <div className="card p-10 text-center">
      <AlertTriangle className="mx-auto mb-2" size={20} style={{ color: '#c0392b' }} />
      <div className="font-semibold text-[13.5px]" style={{ color: '#c0392b' }}>{title}</div>
      {message && <p className="text-sm text-muted mt-1">{message}</p>}
      {onRetry && <button className="btn-secondary mt-4" onClick={onRetry}>Retry</button>}
    </div>
  )
}