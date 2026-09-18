import React from 'react'
import { Link } from 'react-router-dom'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import { RiskBadge, StatusBadge, Progress } from '../UI'
import EmptyState from '../ui/EmptyState'

/**
 * Shared building blocks for the MP / State Nodal / District Authority
 * dashboards.
 *
 * These three cockpits deliberately look like one product. They share a
 * design system, these components, the canonical project ID and the
 * Risk Fusion engine -- what differs is which records reach them and
 * which block each role sees first.
 *
 * Two rules the components below enforce for the whole set:
 *
 *   1. A missing value renders "Data unavailable", never 0 and never a
 *      guess. `physical_progress` genuinely does not exist in the source
 *      dataset, and an officer must be able to tell "we have no reading"
 *      apart from "the reading is zero".
 *
 *   2. Every project links to the EXISTING /projects/:id page using the
 *      canonical work ID. There is no second project-detail screen and
 *      no role-specific identifier.
 */

export const UNAVAILABLE = 'Data unavailable'

export function projectHref(projectId) {
  return `/projects/${encodeURIComponent(projectId)}`
}

/** Number, or an explicit "unavailable" marker -- never a silent zero. */
export function Value({ value, format = formatNumber, suffix = '' }) {
  if (value === null || value === undefined || value === '') {
    return <span className="text-muted text-[12px]">{UNAVAILABLE}</span>
  }
  return <>{format(value)}{suffix}</>
}

export function Percent({ value }) {
  if (value === null || value === undefined) {
    return <span className="text-muted text-[12px]">{UNAVAILABLE}</span>
  }
  return <>{Number(value).toFixed(1)}%</>
}

export function SectionCard({ id, title, subtitle, action, children }) {
  return (
    <section id={id} className="card mb-4 scroll-mt-20">
      <div className="px-4 pt-4 pb-1 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[13.5px] font-semibold text-ink">{title}</h2>
          {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function DataTable({ columns, children, empty }) {
  const hasRows = React.Children.count(children) > 0
  if (!hasRows) {
    return <div className="px-4 pb-4"><EmptyState text={empty} /></div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

/** Compact risk cell: the score and its tier, exactly as Risk Fusion
 * returned them. Never rounded differently per role. */
export function RiskCell({ score, level }) {
  if (score === null || score === undefined) {
    return <span className="text-muted text-[12px]">Not scored</span>
  }
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <span className="font-semibold text-ink">{Number(score).toFixed(1)}</span>
      <RiskBadge risk={level} />
    </div>
  )
}

/**
 * One row of a project table, shared by all three dashboards.
 *
 * `columns` selects which cells appear, so a District Authority can see
 * the MP/constituency column that an MP (who is the constituency) has no
 * use for -- without a second table component existing.
 */
export function ProjectRow({ project, columns = [] }) {
  const cells = {
    id: (
      <td key="id" className="font-mono font-semibold whitespace-nowrap">
        <Link to={projectHref(project.project_id)} className="text-navy hover:underline">
          {project.project_id}
        </Link>
      </td>
    ),
    name: (
      <td key="name" className="max-w-[240px] truncate" title={project.work_description || project.work_category || 'Untitled work'}>
        {project.work_description || project.work_category || 'Untitled work'}
      </td>
    ),
    district: <td key="district" className="whitespace-nowrap">{project.district || '—'}</td>,
    constituency: <td key="constituency" className="whitespace-nowrap">{project.constituency || '—'}</td>,
    mp: <td key="mp" className="whitespace-nowrap max-w-[180px] truncate" title={project.mp_name || ''}>{project.mp_name || '—'}</td>,
    category: <td key="category" className="whitespace-nowrap">{project.work_category || '—'}</td>,
    sanctioned: <td key="sanctioned" className="whitespace-nowrap">{formatCurrency(project.sanctioned_amount)}</td>,
    expenditure: <td key="expenditure" className="whitespace-nowrap">{formatCurrency(project.expenditure)}</td>,
    utilization: <td key="utilization" className="whitespace-nowrap"><Percent value={project.utilization_percent} /></td>,
    progress: (
      <td key="progress" className="min-w-[110px]">
        {project.utilization_percent === null || project.utilization_percent === undefined
          ? <span className="text-xs text-muted">{UNAVAILABLE}</span>
          : <Progress value={Math.max(0, Math.min(100, Number(project.utilization_percent)))} />}
      </td>
    ),
    // Physical progress has no source value anywhere in the canonical
    // dataset. It is shown as explicitly unavailable rather than being
    // derived from financial progress, which would be a different thing
    // wearing this column's name.
    physical: <td key="physical" className="text-xs text-muted whitespace-nowrap">{UNAVAILABLE}</td>,
    status: <td key="status"><StatusBadge status={project.status} /></td>,
    risk: <td key="risk"><RiskCell score={project.risk_score} level={project.risk_level} /></td>,
    signal: (
      <td key="signal" className="max-w-[220px] truncate text-[12.5px]" title={project.top_risk_signal || project.triggered_component || ''}>
        {project.top_risk_signal || project.triggered_component || '—'}
      </td>
    ),
    action: (
      <td key="action" className="whitespace-nowrap">
        <Link to={projectHref(project.project_id)} className="text-xs font-semibold text-navy hover:underline">
          View Details →
        </Link>
      </td>
    ),
  }

  return <tr className="hover:bg-panel">{columns.map(key => cells[key])}</tr>
}

/**
 * Client-side search/sort/paginate over an already-scoped row set.
 *
 * Worth being precise about what this is and is not: the rows have
 * ALREADY been restricted server-side to the caller's jurisdiction, so
 * this only reorders and pages through records the officer is entitled
 * to. It is presentation, not filtering-for-security -- the Project
 * Explorer (/projects) does its searching and paging on the backend.
 */
export function useTableControls(rows, { pageSize = 10 } = {}) {
  const [query, setQuery] = React.useState('')
  const [sortKey, setSortKey] = React.useState('risk_score')
  const [sortAsc, setSortAsc] = React.useState(false)
  const [page, setPage] = React.useState(0)

  React.useEffect(() => { setPage(0) }, [query, sortKey, sortAsc])

  const filtered = React.useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter(row =>
      [row.project_id, row.work_description, row.district, row.constituency, row.work_category, row.mp_name, row.status]
        .some(value => String(value || '').toLowerCase().includes(needle)),
    )
  }, [rows, query])

  const sorted = React.useMemo(() => {
    const copy = [...filtered]
    copy.sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av === bv) return String(a.project_id).localeCompare(String(b.project_id))
      if (av === null || av === undefined) return 1
      if (bv === null || bv === undefined) return -1
      const result = typeof av === 'number' && typeof bv === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv))
      return sortAsc ? result : -result
    })
    return copy
  }, [filtered, sortKey, sortAsc])

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize))
  const pageRows = sorted.slice(page * pageSize, page * pageSize + pageSize)

  function toggleSort(key) {
    if (key === sortKey) setSortAsc(v => !v)
    else { setSortKey(key); setSortAsc(false) }
  }

  return { query, setQuery, sortKey, sortAsc, toggleSort, page, setPage, pageCount, pageRows, total: sorted.length }
}

export function TableControls({ controls, sortOptions, placeholder }) {
  return (
    <div className="px-4 pb-3 flex flex-wrap items-end gap-3">
      <div className="flex-1 min-w-[200px]">
        <label className="text-[11px] font-medium text-muted mb-1 block">Search</label>
        <input
          value={controls.query}
          onChange={e => controls.setQuery(e.target.value)}
          placeholder={placeholder}
          className="w-full border border-line rounded-md py-2 px-3 text-[13px] outline-none focus:border-navy"
        />
      </div>
      <div className="w-full sm:w-auto sm:min-w-[170px]">
        <label className="text-[11px] font-medium text-muted mb-1 block">Sort by</label>
        <select
          value={controls.sortKey}
          onChange={e => controls.toggleSort(e.target.value)}
          className="w-full border border-line rounded-md px-3 py-2 text-[13px] bg-white text-ink"
        >
          {sortOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div className="text-[12.5px] text-muted pb-2">{formatNumber(controls.total)} shown</div>
    </div>
  )
}

export function TablePager({ controls }) {
  if (controls.pageCount <= 1) return null
  return (
    <div className="px-4 py-3 flex items-center justify-between border-t border-line">
      <button
        type="button"
        className="btn-secondary"
        disabled={controls.page === 0}
        onClick={() => controls.setPage(p => Math.max(0, p - 1))}
      >Previous</button>
      <span className="text-xs text-muted">Page {controls.page + 1} of {controls.pageCount}</span>
      <button
        type="button"
        className="btn-secondary"
        disabled={controls.page >= controls.pageCount - 1}
        onClick={() => controls.setPage(p => Math.min(controls.pageCount - 1, p + 1))}
      >Next</button>
    </div>
  )
}

/** The honesty footer: what the source data does and does not support. */
export function DataNotes({ notes }) {
  if (!notes?.length) return null
  return (
    <div className="card p-4">
      <h3 className="text-[12.5px] font-semibold text-ink mb-1.5">About this data</h3>
      <ul className="text-[12px] text-muted space-y-1 list-disc pl-4">
        {notes.map((note, index) => <li key={index}>{note}</li>)}
      </ul>
    </div>
  )
}