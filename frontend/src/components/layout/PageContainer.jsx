import React from 'react'

export default function PageContainer({ children, maxWidth = '1300px', className = '' }) {
  return (
    <div className={`p-4 md:p-6 mx-auto ${className}`} style={{ maxWidth }}>
      {children}
    </div>
  )
}