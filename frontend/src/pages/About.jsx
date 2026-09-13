import React from 'react'
import PublicNavbar from '../components/layout/PublicNavbar'

export default function About() {
  return (
    <div className="min-h-screen bg-panel">
      <PublicNavbar />
      <div className="max-w-[760px] mx-auto px-6 py-12">
        <h1 className="text-[19px] font-semibold text-ink mb-3">About MPLADS AI Shield</h1>
        <p className="text-[13.5px] leading-relaxed text-muted mb-3">
          MPLADS AI Shield is a monitoring layer built on the Members of Parliament Local Area
          Development Scheme (MPLADS) dataset. It combines public transparency reporting with
          project-monitoring workflows and an AI-assisted layer that surfaces financial, timeline,
          duplicate-description and compliance indicators for administrative review.
        </p>
        <p className="text-[13.5px] leading-relaxed text-muted">
          AI Shield identifies indicators requiring review. It does not establish fraud or
          wrongdoing -- every flagged work is reviewed by the relevant authority before any action
          is taken.
        </p>
      </div>
    </div>
  )
}