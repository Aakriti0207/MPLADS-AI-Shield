import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatCount } from '../../lib/publicFormat'

function pageWindow(page, totalPages) {
  const pages = new Set([1, totalPages, page - 1, page, page + 1])
  return [...pages].filter(p => p >= 1 && p <= totalPages).sort((a, b) => a - b)
}

/** "Showing 1-20 of 43,863 projects" + numbered server-side pager. */
export default function PublicPagination({ page, pageSize, total, totalPages, onPage, noun = 'projects' }) {
  if (!total) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  const pages = pageWindow(page, totalPages)

  return (
    <nav aria-label="Pagination" className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-6">
      <p className="text-[14px] text-muted" aria-live="polite">
        Showing <strong className="text-ink">{formatCount(from)}&ndash;{formatCount(to)}</strong> of{' '}
        <strong className="text-ink">{formatCount(total)}</strong> {noun}
      </p>
      <div className="flex items-center gap-1.5">
        <button type="button" className="pub-btn-secondary !px-3 disabled:opacity-40" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft size={16} aria-hidden="true" /> <span className="hidden sm:inline">Previous</span><span className="sm:hidden sr-only">Previous page</span>
        </button>
        <ul className="hidden sm:flex items-center gap-1">
          {pages.map((p, index) => (
            <React.Fragment key={p}>
              {index > 0 && p - pages[index - 1] > 1 && <li aria-hidden="true" className="px-1 text-muted">…</li>}
              <li>
                <button
                  type="button"
                  onClick={() => onPage(p)}
                  aria-current={p === page ? 'page' : undefined}
                  aria-label={`Page ${p}`}
                  className={`min-w-[44px] min-h-[44px] rounded-lg text-[14px] font-semibold ${p === page ? 'bg-navy text-white' : 'text-navy hover:bg-navy-bg'}`}
                >
                  {formatCount(p)}
                </button>
              </li>
            </React.Fragment>
          ))}
        </ul>
        <span className="sm:hidden text-[14px] text-muted px-2">Page {page} of {formatCount(totalPages)}</span>
        <button type="button" className="pub-btn-secondary !px-3 disabled:opacity-40" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
          <span className="hidden sm:inline">Next</span><span className="sm:hidden sr-only">Next page</span> <ChevronRight size={16} aria-hidden="true" />
        </button>
      </div>
    </nav>
  )
}