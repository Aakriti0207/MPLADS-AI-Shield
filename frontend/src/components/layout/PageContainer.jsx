import React from 'react'

/**
 * Shared structural wrapper for application pages: consistent max width,
 * horizontal padding, and vertical spacing so pages don't each redefine
 * their own container padding/margins independently.
 */
export default function PageContainer({ children, maxWidth = '1500px', className = '' }) {
  return (
    <div className={`p-4 md:p-8 mx-auto ${className}`} style={{ maxWidth }}>
      {children}
    </div>
  )
}
