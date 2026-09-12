import React from 'react'
import { AlertTriangle } from 'lucide-react'

export default function ErrorState({ title = 'Could not load data', message, onRetry }) {
  return <div className="card p-10 text-center"><AlertTriangle className="mx-auto text-rose-600 mb-2" size={22}/><div className="font-semibold text-rose-700">{title}</div>{message && <p className="text-sm text-slate-500 mt-1">{message}</p>}{onRetry && <button className="btn-secondary mt-4" onClick={onRetry}>Retry</button>}</div>
}
