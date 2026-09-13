import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'

// Reference nav item set for the unauthenticated shell (design-system
// spec). "Projects" and "AI Insights" point at the real, already-built
// /projects and /ai-shield routes -- those are behind ProtectedRoute
// today, so an anonymous visitor following them lands on /login and is
// bounced back afterwards (see Login.jsx's redirectTo handling). Making
// those views actually public is a product decision for a later pass,
// not part of this foundation-only revamp.
const NAV_ITEMS = [
  { to: '/', label: 'Overview' },
  { to: '/projects', label: 'Projects' },
  { to: '/ai-shield', label: 'AI Insights' },
  { to: '/about', label: 'About' },
]

/**
 * Shared unauthenticated-shell navbar: white background, bottom hairline,
 * 1200px centered content, brand mark + tagline, nav links, and a
 * Secure Login CTA. Mirrors AuthSidebar's structure for the logged-in
 * shell so the two chrome pieces read as one product.
 */
export default function PublicNavbar() {
  const location = useLocation()

  return (
    <div className="sticky top-0 z-20 bg-white border-b border-line">
      <div className="max-w-[1200px] mx-auto px-5 md:px-6 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md flex items-center justify-center bg-navy">
            <ShieldCheck size={17} color="white" aria-hidden="true" />
          </div>
          <div className="leading-tight">
            <div className="text-[14px] font-bold tracking-tight text-navy">MPLADS AI Shield</div>
            <div className="text-[10px] text-muted">AI-Powered Project Monitoring</div>
          </div>
        </Link>

        <nav aria-label="Primary" className="hidden md:flex items-center gap-6">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname === item.to
            return (
              <Link
                key={item.to}
                to={item.to}
                className="text-[13px] font-medium pb-0.5"
                style={{
                  color: active ? '#0b2e4f' : '#55636e',
                  borderBottom: active ? '2px solid #0b2e4f' : '2px solid transparent',
                }}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>

        <Link to="/login" className="text-[12.5px] font-semibold px-3.5 py-1.5 rounded bg-navy text-white">
          Secure Login
        </Link>
      </div>
    </div>
  )
}