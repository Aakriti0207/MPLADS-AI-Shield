import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

// Shared prev/next pager for the "skip/limit"-style endpoints (Projects,
// Alerts) -- the backend has no total-count field, so this deliberately
// shows only a page number and a disabled state at each end rather than
// a fabricated "Page X of Y" total.
export default function Pagination({ page, canGoPrev, canGoNext, onPrev, onNext }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-line">
      <button
        disabled={!canGoPrev}
        onClick={onPrev}
        className="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"
      ><ChevronLeft size={15} /> Previous</button>
      <span className="text-xs text-muted">Page {page}</span>
      <button
        disabled={!canGoNext}
        onClick={onNext}
        className="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"
      >Next <ChevronRight size={15} /></button>
    </div>
  )
}