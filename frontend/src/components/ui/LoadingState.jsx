import React from 'react'
import { Loader2 } from 'lucide-react'

export default function LoadingState({ text = 'Loading…' }) {
  return (
    <div className="card p-14 flex flex-col items-center gap-2 text-muted">
      <Loader2 className="animate-spin" size={20} />
      <span className="text-sm">{text}</span>
    </div>
  )
}