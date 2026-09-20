import React from 'react'

/** Decorative placeholder block. Always paired with a live-region label. */
export function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

/** Wrapper that announces "Loading" once to assistive tech. */
export function LoadingRegion({ label = 'Loading', children, className = '' }) {
  return (
    <div role="status" aria-busy="true" aria-live="polite" className={className}>
      <span className="sr-only">{label}…</span>
      {children}
    </div>
  )
}

export function StatCardSkeleton() {
  return (
    <div className="pub-card p-5">
      <Skeleton className="h-9 w-9 rounded-full" />
      <Skeleton className="h-8 w-28 mt-4" />
      <Skeleton className="h-4 w-24 mt-3" />
      <Skeleton className="h-3 w-full mt-3" />
    </div>
  )
}

export function ProjectCardSkeleton() {
  return (
    <div className="pub-card p-5">
      <div className="flex gap-2"><Skeleton className="h-6 w-24" /><Skeleton className="h-6 w-32" /></div>
      <Skeleton className="h-5 w-11/12 mt-4" />
      <Skeleton className="h-5 w-2/3 mt-2" />
      <Skeleton className="h-4 w-1/2 mt-4" />
      <div className="grid grid-cols-2 gap-3 mt-5"><Skeleton className="h-10" /><Skeleton className="h-10" /></div>
      <Skeleton className="h-2 w-full mt-5" />
    </div>
  )
}

export function ChartSkeleton({ height = 260 }) {
  return (
    <div className="pub-card p-5">
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-4 w-2/3 mt-2" />
      <Skeleton className="w-full mt-5" style={{ height }} />
    </div>
  )
}