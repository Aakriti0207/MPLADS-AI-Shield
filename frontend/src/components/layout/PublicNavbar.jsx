import React, { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Landmark, LockKeyhole, Menu, Search, X } from 'lucide-react'
import { PORTAL_PATHS, projectsLink } from '../../lib/publicTheme'

// Five items, no more: the public portal is for citizens, not analysts.
const NAV_ITEMS = [
  { to: PORTAL_PATHS.home, label: 'Home', end: true },
  { to: PORTAL_PATHS.projects, label: 'Projects' },
  { to: PORTAL_PATHS.map, label: 'Explore Map' },
  { to: PORTAL_PATHS.statistics, label: 'Statistics' },
  { to: PORTAL_PATHS.about, label: 'About MPLADS' },
]

function HeaderSearch({ onDone, className = '' }) {
  const navigate = useNavigate()
  const [value, setValue] = useState('')

  function submit(event) {
    event.preventDefault()
    navigate(projectsLink({ q: value.trim() }))
    setValue('')
    if (onDone) onDone()
  }

  return (
    <form role="search" onSubmit={submit} className={`relative ${className}`}>
      <label htmlFor={`header-search-${className ? 'm' : 'd'}`} className="sr-only">Search projects</label>
      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none" aria-hidden="true" />
      <input
        id={`header-search-${className ? 'm' : 'd'}`}
        type="search"
        value={value}
        onChange={event => setValue(event.target.value)}
        placeholder="Search projects"
        className="pub-input pl-9 !py-2 !min-h-[40px] text-[14px]"
      />
    </form>
  )
}

/**
 * Public transparency portal header.
 *
 * PUBLIC navigation (left/centre) is visually and structurally separate
 * from OFFICIAL / AUTHORIZED ACCESS (right, behind a divider), so a
 * citizen never confuses the open portal with the internal tools.
 */
export default function PublicNavbar() {
  const location = useLocation()
  const [open, setOpen] = useState(false)

  useEffect(() => { setOpen(false) }, [location.pathname])

  useEffect(() => {
    if (!open) return undefined
    const onKey = event => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const linkClass = ({ isActive }) =>
    `px-3 py-2 text-[14.5px] font-semibold rounded-md border-b-2 whitespace-nowrap ${
      isActive ? 'text-navy border-blue' : 'text-muted border-transparent hover:text-navy'
    }`

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-line">
      <div className="max-w-[1200px] mx-auto px-4 md:px-6 h-16 flex items-center justify-between gap-4">
        <Link to={PORTAL_PATHS.home} className="flex items-center gap-3 shrink-0" aria-label="MPLADS Public Transparency Portal - home">
          <span className="w-10 h-10 rounded-lg bg-navy flex items-center justify-center" aria-hidden="true">
            <Landmark size={20} color="white" />
          </span>
          <span className="leading-tight">
            <span className="block text-[17px] font-bold tracking-tight text-navy">MPLADS</span>
            <span className="block text-[11.5px] text-muted font-medium">Public Transparency Portal</span>
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden lg:flex items-center gap-1">
          {NAV_ITEMS.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>{item.label}</NavLink>
          ))}
        </nav>

        <div className="hidden lg:flex items-center gap-4">
          <HeaderSearch className="w-[200px]" />
          <span className="h-6 w-px bg-line" aria-hidden="true" />
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 whitespace-nowrap text-[13.5px] font-semibold text-navy border border-line rounded-lg px-3 py-2 hover:bg-navy-bg"
            title="For authorized MPLADS officials only"
          >
            <LockKeyhole size={14} aria-hidden="true" /> Official Login
          </Link>
        </div>

        <button
          type="button"
          className="lg:hidden inline-flex items-center justify-center w-11 h-11 rounded-lg border border-line text-navy"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? 'Close menu' : 'Open menu'}
          onClick={() => setOpen(value => !value)}
        >
          {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
        </button>
      </div>

      {open && (
        <div id="mobile-menu" className="lg:hidden border-t border-line bg-white px-4 pb-4 pt-3">
          <HeaderSearch onDone={() => setOpen(false)} className="mb-3 !w-full" />
          <nav aria-label="Primary mobile" className="flex flex-col">
            {NAV_ITEMS.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `px-3 py-3 text-[16px] font-semibold rounded-lg ${isActive ? 'bg-navy-bg text-navy' : 'text-ink'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-3 pt-3 border-t border-line">
            <p className="text-[12px] text-muted mb-2">For authorized officials</p>
            <Link to="/login" className="pub-btn-secondary w-full">
              <LockKeyhole size={15} aria-hidden="true" /> Official Login
            </Link>
          </div>
        </div>
      )}
    </header>
  )
}