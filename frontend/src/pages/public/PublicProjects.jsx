import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import PublicLayout from '../../components/public/PublicLayout'
import ProjectCard from '../../components/public/ProjectCard'
import FilterPanel from '../../components/public/FilterPanel'
import PublicPagination from '../../components/public/PublicPagination'
import DataFreshness from '../../components/public/DataFreshness'
import { PageHeading, PublicEmpty, PublicError } from '../../components/public/PublicStates'
import { LoadingRegion, ProjectCardSkeleton } from '../../components/public/Skeleton'
import usePublicQuery from '../../lib/usePublicQuery'
import { fetchExplorerFilters, fetchExplorerProjects, fetchPublicMeta } from '../../features/public/api'
import { formatCount, titleCase } from '../../lib/publicFormat'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 350
const SORTS = [
  ['recent', 'Most recent activity'],
  ['sanctioned_desc', 'Highest sanctioned amount'],
  ['expenditure_desc', 'Highest expenditure'],
]
const EMPTY_OPTIONS = { states: [], districts: [], categories: [], statuses: [], years: [] }

/**
 * Public Project Explorer -- the core of the portal.
 *
 * All searching, filtering, sorting and paging is done by the backend
 * (GET /public/explorer/projects); the browser only ever holds one page
 * of 20 projects. Every control is mirrored in the URL, so a filtered
 * view can be bookmarked or shared and the Back button behaves.
 */
export default function PublicProjects() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const filters = {
    state: params.get('state') || '',
    district: params.get('district') || '',
    category: params.get('category') || '',
    status: params.get('status') || '',
    year: params.get('year') || '',
  }
  const sort = SORTS.some(([value]) => value === params.get('sort')) ? params.get('sort') : 'recent'
  const page = Math.max(1, parseInt(params.get('page') || '1', 10) || 1)

  const update = useCallback((changes, { resetPage = true } = {}) => {
    setParams(prev => {
      const next = new URLSearchParams(prev)
      Object.entries(changes).forEach(([key, value]) => {
        if (value === '' || value === null || value === undefined) next.delete(key)
        else next.set(key, String(value))
      })
      if (resetPage) next.delete('page')
      return next
    }, { replace: false })
  }, [setParams])

  // --- search box: local text, debounced into the URL ------------------
  const [text, setText] = useState(q)
  useEffect(() => { setText(q) }, [q])
  useEffect(() => {
    if (text.trim() === q.trim()) return undefined
    const timer = setTimeout(() => update({ q: text.trim() }), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [text]) // eslint-disable-line react-hooks/exhaustive-deps

  // --- filter options (districts follow the staged state) --------------
  const [draftState, setDraftState] = useState(filters.state)
  useEffect(() => { setDraftState(filters.state) }, [filters.state])
  const optionsQuery = usePublicQuery(opts => fetchExplorerFilters({ state: draftState || null }, opts), [draftState])
  const options = optionsQuery.data || EMPTY_OPTIONS

  const meta = usePublicQuery(opts => fetchPublicMeta(opts), [])

  // --- results ----------------------------------------------------------
  const results = usePublicQuery(
    opts => fetchExplorerProjects({ search: q, ...filters, year: filters.year || null, sort, page, pageSize: PAGE_SIZE }, opts),
    [q, filters.state, filters.district, filters.category, filters.status, filters.year, sort, page]
  )

  const headingRef = useRef(null)
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [page])

  const chips = useMemo(() => {
    const list = []
    if (q) list.push({ key: 'q', label: `Search: “${q}”` })
    if (filters.state) list.push({ key: 'state', label: `State: ${filters.state}`, also: ['district'] })
    if (filters.district) list.push({ key: 'district', label: `District: ${titleCase(filters.district)}` })
    if (filters.status) list.push({ key: 'status', label: `Status: ${filters.status}` })
    if (filters.category) list.push({ key: 'category', label: `Category: ${filters.category}` })
    if (filters.year) list.push({ key: 'year', label: `Sanction year: ${filters.year}` })
    return list
  }, [q, filters.state, filters.district, filters.status, filters.category, filters.year])

  const clearAll = () => { setText(''); setDraftState(''); setParams(new URLSearchParams(sort !== 'recent' ? { sort } : {})) }
  const data = results.data
  const hasAny = chips.length > 0

  return (
    <PublicLayout>
      <PageHeading
        eyebrow="Project explorer"
        title="Explore MPLADS Projects"
        description="Search sanctioned works and see what was approved, what has been spent and where each project stands."
      />

      <form role="search" onSubmit={event => { event.preventDefault(); update({ q: text.trim() }) }} className="mb-5">
        <label htmlFor="project-search" className="pub-label">Search projects</label>
        <div className="relative">
          <Search size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" aria-hidden="true" />
          <input
            id="project-search"
            type="search"
            value={text}
            onChange={event => setText(event.target.value)}
            placeholder="Search by project name, project ID, district, state or constituency"
            className="pub-input pl-11 !min-h-[52px] text-[16px]"
            autoComplete="off"
          />
        </div>
      </form>

      <div className="grid gap-6 lg:grid-cols-[290px_minmax(0,1fr)] items-start">
        <FilterPanel
          className="lg:sticky lg:top-24"
          value={filters}
          options={options}
          onDraftStateChange={setDraftState}
          onApply={next => update(next)}
        />

        <section aria-labelledby="results-title" aria-busy={results.loading}>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <h2 id="results-title" ref={headingRef} className="text-[18px] font-bold text-navy" aria-live="polite">
              {data ? `${formatCount(data.total)} project${data.total === 1 ? '' : 's'} found` : 'Projects'}
            </h2>
            <div className="flex items-center gap-2">
              <label htmlFor="sort" className="text-[13.5px] text-muted">Sort by</label>
              <select id="sort" className="pub-input !w-auto" value={sort} onChange={event => update({ sort: event.target.value === 'recent' ? '' : event.target.value })}>
                {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
          </div>

          {hasAny && (
            <ul className="flex flex-wrap items-center gap-2 mb-4" aria-label="Active filters">
              {chips.map(chip => (
                <li key={chip.key}>
                  <button
                    type="button"
                    onClick={() => {
                      if (chip.key === 'q') setText('')
                      update({ [chip.key]: '', ...(chip.also ? Object.fromEntries(chip.also.map(k => [k, ''])) : {}) })
                    }}
                    className="inline-flex items-center gap-1.5 rounded-full bg-navy-bg text-navy text-[13px] font-semibold pl-3 pr-2 py-1.5 min-h-[36px]"
                    aria-label={`Remove filter ${chip.label}`}
                  >
                    {chip.label} <X size={14} aria-hidden="true" />
                  </button>
                </li>
              ))}
              <li><button type="button" onClick={clearAll} className="text-[13.5px] font-semibold text-blue hover:underline px-2 min-h-[36px]">Clear all</button></li>
            </ul>
          )}

          {results.error ? (
            <PublicError onRetry={results.retry} />
          ) : !data ? (
            <LoadingRegion label="Loading projects" className="grid gap-4 md:grid-cols-2">
              {[0, 1, 2, 3, 4, 5].map(i => <ProjectCardSkeleton key={i} />)}
            </LoadingRegion>
          ) : data.items.length === 0 ? (
            <PublicEmpty
              action={hasAny ? <button type="button" className="pub-btn-secondary mt-5" onClick={clearAll}>Clear all filters</button> : null}
            />
          ) : (
            <>
              <ul className={`grid gap-4 md:grid-cols-2 transition-opacity ${results.refreshing ? 'opacity-60' : ''}`}>
                {data.items.map(project => <li key={project.id}><ProjectCard project={project} /></li>)}
              </ul>
              <PublicPagination
                page={data.page}
                pageSize={data.pageSize}
                total={data.total}
                totalPages={data.totalPages}
                onPage={next => update({ page: next === 1 ? '' : next }, { resetPage: false })}
              />
            </>
          )}
        </section>
      </div>

      <DataFreshness meta={meta.data} className="mt-10" />
    </PublicLayout>
  )
}