import React, { useEffect, useId, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Search } from 'lucide-react'
import { fetchExplorerProjects } from '../../features/public/api'
import { formatInr, titleCase } from '../../lib/publicFormat'
import { projectsLink, publicProjectPath } from '../../lib/publicTheme'
import StatusPill from './StatusPill'

const MIN_CHARS = 3
const DEBOUNCE_MS = 300

/**
 * Hero search with live suggestions (ARIA combobox).
 * As the citizen types, matching projects come from the server-side
 * search (never a client-side scan). Enter opens the full results.
 */
export default function SearchBox({ placeholder = 'Search by project name, project ID, district, state or constituency' }) {
  const navigate = useNavigate()
  const listId = useId()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const wrapRef = useRef(null)

  useEffect(() => {
    const text = query.trim()
    if (text.length < MIN_CHARS) {
      setResults([]); setTotal(0); setLoading(false); setFailed(false)
      return undefined
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setLoading(true); setFailed(false)
      fetchExplorerProjects({ search: text, pageSize: 5 }, { signal: controller.signal })
        .then(page => { setResults(page.items); setTotal(page.total); setActive(-1) })
        .catch(error => { if (error?.name !== 'AbortError') setFailed(true) })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, DEBOUNCE_MS)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query])

  useEffect(() => {
    const onClick = event => { if (wrapRef.current && !wrapRef.current.contains(event.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const showPanel = open && query.trim().length >= MIN_CHARS

  function submit(event) {
    event.preventDefault()
    if (active >= 0 && results[active]) {
      navigate(publicProjectPath(results[active].id))
      return
    }
    navigate(projectsLink({ q: query.trim() }))
  }

  function onKeyDown(event) {
    if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); setActive(i => Math.min(i + 1, results.length - 1)) }
    else if (event.key === 'ArrowUp') { event.preventDefault(); setActive(i => Math.max(i - 1, -1)) }
    else if (event.key === 'Escape') { setOpen(false) }
  }

  return (
    <div ref={wrapRef} className="relative">
      <form role="search" onSubmit={submit} className="flex flex-col sm:flex-row gap-2.5">
        <div className="relative flex-1">
          <label htmlFor="hero-search" className="sr-only">Search MPLADS projects</label>
          <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" aria-hidden="true" />
          <input
            id="hero-search"
            type="search"
            role="combobox"
            aria-expanded={showPanel}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
            autoComplete="off"
            value={query}
            onChange={event => { setQuery(event.target.value); setOpen(true) }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            className="pub-input pl-11 !min-h-[52px] text-[16px]"
          />
        </div>
        <button type="submit" className="pub-btn-primary !min-h-[52px] sm:px-7">Search</button>
      </form>

      {showPanel && (
        <div id={listId} role="listbox" aria-label="Matching projects"
          className="absolute z-20 left-0 right-0 mt-2 pub-card shadow-xl overflow-hidden text-left">
          {loading && (
            <div className="flex items-center gap-2 px-4 py-3 text-[14px] text-muted" role="status">
              <Loader2 size={16} className="animate-spin" aria-hidden="true" /> Searching projects…
            </div>
          )}
          {!loading && failed && <div className="px-4 py-3 text-[14px] text-muted" role="status">We couldn't search right now. Press Search to try again.</div>}
          {!loading && !failed && results.length === 0 && (
            <div className="px-4 py-3 text-[14px] text-muted" role="status">No projects found. Try another name, district or category.</div>
          )}
          {!failed && results.map((project, index) => (
            <div
              id={`${listId}-${index}`}
              key={project.id}
              role="option"
              aria-selected={index === active}
              onMouseEnter={() => setActive(index)}
              onClick={() => navigate(publicProjectPath(project.id))}
              className={`px-4 py-3 cursor-pointer border-t border-line first:border-t-0 ${index === active ? 'bg-navy-bg' : ''}`}
            >
              <div className="text-[14.5px] font-semibold text-ink line-clamp-1">{project.title || 'Project description not recorded'}</div>
              <div className="mt-0.5 text-[13px] text-muted">
                {[titleCase(project.district), project.state].filter(Boolean).join(', ') || 'Location not recorded'}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-muted">
                <StatusPill status={project.status} />
                <span>Sanctioned: <strong className="text-ink">{formatInr(project.sanctioned) ?? 'Not available'}</strong></span>
                <span>Spent: <strong className="text-ink">{project.expenditure !== null ? formatInr(project.expenditure) : 'Not recorded'}</strong></span>
              </div>
            </div>
          ))}
          {!loading && !failed && total > results.length && (
            <button type="button" onClick={() => navigate(projectsLink({ q: query.trim() }))}
              className="w-full text-left px-4 py-3 border-t border-line text-[14px] font-semibold text-blue hover:bg-navy-bg">
              See all {total.toLocaleString('en-IN')} matching projects
            </button>
          )}
        </div>
      )}
    </div>
  )
}