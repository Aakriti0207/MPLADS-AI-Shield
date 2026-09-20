import React from 'react'
import { Link } from 'react-router-dom'
import { Eye } from 'lucide-react'
import PublicNavbar from '../layout/PublicNavbar'
import { PORTAL_PATHS } from '../../lib/publicTheme'

/**
 * Shared frame for every public-portal page: skip link, header, a single
 * <main> landmark and the footer. Everything is scoped by the
 * `.public-portal` class so the internal app's styles are unaffected.
 */
export default function PublicLayout({ children, width = 'max-w-[1440px]' }) {
  return (
    <div className="public-portal min-h-screen flex flex-col">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <PublicNavbar />
      <main id="main-content" tabIndex={-1} className={`${width} w-full mx-auto pub-px py-6 md:py-10 flex-1`}>
        {children}
      </main>
      <PublicFooter />
    </div>
  )
}

function PublicFooter() {
  return (
    <footer className="bg-white border-t border-line">
      <div className="max-w-[1440px] mx-auto pub-px py-8 grid gap-8 md:grid-cols-3">
        <div>
          <div className="text-[16px] font-bold text-navy">MPLADS</div>
          <div className="text-[13px] text-muted">Public Transparency Portal</div>
          <p className="text-[13px] text-muted mt-3 max-w-[320px]">
            A public window into MPLADS project records: what is sanctioned, what is spent and where.
          </p>
        </div>
        <nav aria-label="Footer">
          <div className="text-[13px] font-semibold text-ink mb-2">Explore</div>
          <ul className="space-y-1.5 text-[14px]">
            <li><Link className="text-blue hover:underline" to={PORTAL_PATHS.about}>About MPLADS</Link></li>
            <li><Link className="text-blue hover:underline" to={PORTAL_PATHS.projects}>Projects</Link></li>
            <li><Link className="text-blue hover:underline" to={PORTAL_PATHS.map}>Explore Map</Link></li>
            <li><Link className="text-blue hover:underline" to={PORTAL_PATHS.statistics}>Statistics</Link></li>
          </ul>
        </nav>
        <div>
          <div className="text-[13px] font-semibold text-ink mb-2 flex items-center gap-1.5">
            <Eye size={14} aria-hidden="true" /> Transparency note
          </div>
          <p className="text-[13px] text-muted">
            Figures are aggregated from published MPLADS project records. Fields with no recorded value are
            shown as not available rather than estimated. This is a public transparency view, not an
            official Government of India portal.
          </p>
        </div>
      </div>
    </footer>
  )
}