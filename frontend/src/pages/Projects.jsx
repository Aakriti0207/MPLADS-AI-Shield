import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { formatCurrency, formatNumber } from '../lib/formatters'
import { RiskBadge, StatusBadge, Progress } from '../components/UI'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import Pagination from '../components/ui/Pagination'
import {
  fetchProjectPage,
  fetchProjectFilterOptions,
  fetchPublicProjectPage,
  fetchDemoProjectPage,
} from '../features/projects/api'
import ScopeBanner from '../components/layout/ScopeBanner'
import { pageTitleFor } from '../lib/roles'
import ProjectFilters from '../components/projects/ProjectFilters'
import PageContainer from '../components/layout/PageContainer'
import AuthenticatedShell from '../components/layout/AuthenticatedShell'
import PublicNavbar from '../components/layout/PublicNavbar'
import { useAuth } from '../context/AuthContext'

const PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 350

const PROJECT_SECTORS = [
  'Agriculture & Irrigation',
  'Community & Public Buildings',
  'Education',
  'Electricity & Energy',
  'Environment & Green Infrastructure',
  'Healthcare',
  'Other Public Infrastructure',
  'Public Utilities',
  'Roads & Connectivity',
  'Social Welfare',
  'Sports & Recreation',
  'Water & Sanitation',
]

const TABLE_COLUMNS = [
  'Work ID',
  'Project / Work',
  'State',
  'District',
  'Constituency',
  'MP Type',
  'MP',
  'Status',
  'Sanctioned',
  'Expenditure',
  'Progress',
]

// Clean MP display names without modifying backend/source data.
function cleanMpName(value) {
  const text = String(value ?? '').trim()

  if (!text) return null

  // Hide missing year metadata without changing the underlying source data.
  const cleaned = text
    .replace(/\s*\(NaN-NaN\)\s*$/i, '')
    .trim()

  return cleaned || null
}

// Real financial_progress from the backend wins when present.
// Otherwise safely derive it from sanctioned/expenditure.
// Result is clamped between 0 and 100.
function financialProgressPct(project) {
  if (
    project.financialProgress !== null &&
    project.financialProgress !== undefined
  ) {
    const n = Number(project.financialProgress)

    if (Number.isFinite(n)) {
      return Math.max(0, Math.min(100, n))
    }
  }

  if (
    project.sanctioned &&
    project.expenditure !== null &&
    project.expenditure !== undefined
  ) {
    const n =
      (Number(project.expenditure) / Number(project.sanctioned)) * 100

    if (Number.isFinite(n)) {
      return Math.max(0, Math.min(100, Math.round(n)))
    }
  }

  return null
}

/**
 * Project Explorer
 *
 * Data source:
 *
 * Anonymous visitor
 *   -> GET /public/projects/query
 *
 * Authenticated real session
 *   -> GET /projects/query
 *
 * Demo session
 *   -> GET /demo/projects/query
 *
 * Demo sessions use the dedicated demo API because they do not
 * carry a real JWT. The demo API provides the current canonical
 * project universe together with Risk Fusion results.
 */
export default function Projects() {
  const { status, isAuthenticated, isDemo, role } = useAuth()
  const navigate = useNavigate()

  const authReady = status !== 'checking'

  const useProtectedApi = isAuthenticated && !isDemo
  const useDemoApi = isAuthenticated && isDemo

  const [rawQuery, setRawQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')

  // A district may arrive as a query param -- the State Nodal
  // dashboard's district drill-down links here with ?district=NAME.
  // It is still only a NARROWING filter: the backend refuses any
  // district outside the caller's authorized state.
  const [searchParams, setSearchParams] = useSearchParams()

  const [stateFilter, setStateFilter] = useState('All')
  const [districtFilter, setDistrictFilter] = useState(searchParams.get('district') || 'All')
  const [categoryFilter, setCategoryFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')

  // Scope + option lists, both supplied by the backend.
  const [scope, setScope] = useState(null)
  const [lockedFilters, setLockedFilters] = useState([])
  const [districtOptions, setDistrictOptions] = useState([])
  const [scopeMessage, setScopeMessage] = useState(null)

  const [skip, setSkip] = useState(0)

  const [items, setItems] = useState([])
  const [total, setTotal] = useState(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [stateOptions, setStateOptions] = useState([])
  const [categoryOptions, setCategoryOptions] =
    useState(PROJECT_SECTORS)

  // Debounce free-text search.
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(rawQuery)
      setSkip(0)
    }, SEARCH_DEBOUNCE_MS)

    return () => clearTimeout(timer)
  }, [rawQuery])

  function handleStateChange(value) {
    setStateFilter(value)
    setSkip(0)
  }

  function handleDistrictChange(value) {
    setDistrictFilter(value)
    setSkip(0)
    const next = new URLSearchParams(searchParams)
    if (value && value !== 'All') next.set('district', value)
    else next.delete('district')
    setSearchParams(next, { replace: true })
  }

  function handleCategoryChange(value) {
    setCategoryFilter(value)
    setSkip(0)
  }

  function handleStatusChange(value) {
    setStatusFilter(value)
    setSkip(0)
  }

  function handleReset() {
    setStateFilter('All')
    setDistrictFilter('All')
    setSearchParams(new URLSearchParams(), { replace: true })
    setCategoryFilter('All')
    setStatusFilter('All')
    setRawQuery('')
    setDebouncedQuery('')
    setSkip(0)
  }

  const filters = useMemo(
    () => ({
      skip,
      limit: PAGE_SIZE,
      state: stateFilter,
      district: districtFilter,
      category: categoryFilter,
      status: statusFilter,
      search: debouncedQuery,
    }),
    [
      skip,
      stateFilter,
      districtFilter,
      categoryFilter,
      statusFilter,
      debouncedQuery,
    ],
  )

  // Main project list.
  //
  // Demo MUST use /demo/projects/query.
  // Real authenticated users use /projects/query.
  // Anonymous users use /public/projects/query.
  useEffect(() => {
    if (!authReady) return

    let cancelled = false

    setLoading(true)
    setError(null)

    const fetcher = useDemoApi
      ? fetchDemoProjectPage
      : useProtectedApi
        ? fetchProjectPage
        : fetchPublicProjectPage

    fetcher(filters)
      .then((data) => {
        if (cancelled) return

        setItems(data.items || [])

        // The scope the BACKEND actually applied, echoed on the
        // response. Rendered verbatim so the page states what it really
        // filtered on rather than what the filter bar happens to show.
        if (data.scope) setScope(data.scope)
        setScopeMessage(data.empty_state_message || null)

        setTotal(
          data.total ??
            data.total_count ??
            data.count ??
            null,
        )
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.message || 'Failed to reach the API',
          )
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [
    authReady,
    useProtectedApi,
    useDemoApi,
    filters,
  ])

  // Load the scope-aware filter-options payload.
  //
  // This replaces an inline fetch('/projects/filter-options') that used
  // neither the configured API base nor the Authorization header, and so
  // never actually returned anything. It now goes through the shared
  // api layer, and the endpoint itself returns only values present in
  // the caller's authorized records -- which is what makes the filter
  // bar role-aware rather than merely visually trimmed.
  useEffect(() => {
    if (!authReady || (!useProtectedApi && !useDemoApi)) return

    let cancelled = false

    fetchProjectFilterOptions()
      .then((data) => {
        if (cancelled || !data) return

        if (Array.isArray(data.states) && data.states.length) {
          setStateOptions(data.states)
        }

        if (Array.isArray(data.districts)) {
          setDistrictOptions(data.districts)
        }

        if (Array.isArray(data.locked_filters)) {
          setLockedFilters(data.locked_filters)
        }

        if (data.scope) setScope(data.scope)

        const categories = Array.isArray(data.categories)
          ? data.categories.filter(Boolean)
          : []

        const mergedCategories = [
          ...new Set([...PROJECT_SECTORS, ...categories]),
        ].sort((a, b) => a.localeCompare(b))

        if (mergedCategories.length) {
          setCategoryOptions(mergedCategories)
        }
      })
      .catch(() => {
        // Progressive enhancement only. If this fails the explorer still
        // works -- the backend scopes the results regardless of what the
        // filter bar was able to offer.
      })

    return () => {
      cancelled = true
    }
  }, [
    authReady,
    useProtectedApi,
    useDemoApi,
  ])

  // Fallback filter options from loaded rows.
  // workType is the normalized project sector returned by the API.
  useEffect(() => {
    if (
      stateOptions.length === 0 &&
      items.length > 0
    ) {
      setStateOptions(
        [
          ...new Set(
            items
              .map((project) => project.state)
              .filter(Boolean),
          ),
        ].sort(),
      )
    }

    // Keep the complete supported sector taxonomy visible.
    // Do not replace it with only the sectors present on the current page.

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items])

  const anyRiskScore = items.some(
    (project) =>
      project.riskScore !== null &&
      project.riskScore !== undefined,
  )

  const riskColumnLabel = anyRiskScore
    ? 'Risk Score'
    : 'AI Shield'

  const countLabel =
    total !== null
      ? `${formatNumber(total)} projects`
      : `${items.length} project${
          items.length === 1 ? '' : 's'
        } on this page`

  const content = (
    <PageContainer>
      <div className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">
          {pageTitleFor('/projects', role, 'Project Explorer')}
        </h1>

        <p className="text-[13px] text-muted mt-0.5">
          Browse MPLADS works and inspect their financial,
          execution and risk context.
        </p>
      </div>

      {/* States the jurisdiction these results were filtered to, using
          the backend's own answer rather than the filter selections. */}
      {isAuthenticated && scope && <ScopeBanner scope={scope} />}

      <ProjectFilters
        query={rawQuery}
        onQueryChange={setRawQuery}
        state={stateFilter}
        onStateChange={handleStateChange}
        states={stateOptions}
        district={districtFilter}
        onDistrictChange={handleDistrictChange}
        districts={districtOptions}
        category={categoryFilter}
        onCategoryChange={handleCategoryChange}
        categories={categoryOptions}
        status={statusFilter}
        onStatusChange={handleStatusChange}
        onReset={handleReset}
        lockedFilters={lockedFilters}
        scope={scope}
      />

      {!loading && !error && (
        <div className="mb-2 text-[12.5px] text-muted">
          {countLabel}
        </div>
      )}

      <div className="card overflow-hidden">
        {loading && (
          <LoadingState text="Loading projects from the API…" />
        )}

        {!loading && error && (
          <ErrorState
            title="Could not load projects"
            message={error}
            onRetry={() => setSkip((s) => s)}
          />
        )}

        {!loading && !error && (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  {[
                    ...TABLE_COLUMNS,
                    riskColumnLabel,
                  ].map((header) => (
                    <th key={header}>{header}</th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {items.map((project) => {
                  const pct =
                    financialProgressPct(project)

                  const hasRisk =
                    (project.riskScore !== null &&
                      project.riskScore !== undefined) ||
                    project.risk

                  const projectUrl = project.id
                    ? `/projects/${encodeURIComponent(
                        project.id,
                      )}`
                    : '#'

                  return (
                    <tr
                      key={project.id}
                      className="hover:bg-panel cursor-pointer"
                      onClick={() => {
                        if (project.id) {
                          navigate(projectUrl)
                        }
                      }}
                    >
                      <td className="font-mono font-semibold whitespace-nowrap">
                        {project.id ? (
                          <Link
                            to={projectUrl}
                            onClick={(event) =>
                              event.stopPropagation()
                            }
                            className="text-navy hover:underline"
                          >
                            {project.id}
                          </Link>
                        ) : (
                          '—'
                        )}
                      </td>

                      <td
                        className="max-w-[220px] truncate"
                        title={
                          project.workDescription ||
                          project.workType ||
                          'Untitled work'
                        }
                      >
                        {project.workDescription ||
                          project.workType ||
                          'Untitled work'}
                      </td>

                      <td className="whitespace-nowrap">
                        {project.state || '—'}
                      </td>

                      <td className="whitespace-nowrap">
                        {project.district || '—'}
                      </td>

                      {/* 
                        IMPORTANT:
                        The backend now supplies the project-location
                        constituency. Do NOT replace it with the state
                        for Rajya Sabha projects.
                      */}
                      <td
                        className="whitespace-nowrap"
                        title={
                          project.constituency ||
                          'Project-location constituency could not be determined from the available source data.'
                        }
                      >
                        {project.constituency ||
                          'Not determinable'}
                      </td>

                      <td className="whitespace-nowrap">
                        {String(project?.mpType ?? '').trim() ||
                          '—'}
                      </td>

                      <td className="whitespace-nowrap">
                        {cleanMpName(project.mpName) || '—'}
                      </td>

                      <td>
                        <StatusBadge
                          status={project.status}
                        />
                      </td>

                      <td className="whitespace-nowrap">
                        {formatCurrency(
                          project.sanctioned,
                        )}
                      </td>

                      <td className="whitespace-nowrap">
                        {formatCurrency(
                          project.expenditure,
                        )}
                      </td>

                      <td className="min-w-[110px]">
                        {pct === null ? (
                          <span className="text-xs text-muted">
                            Not available
                          </span>
                        ) : (
                          <Progress value={pct} />
                        )}
                      </td>

                      <td>
                        {hasRisk ? (
                          <div className="flex items-center gap-2">
                            {project.riskScore !== null &&
                              project.riskScore !==
                                undefined && (
                                <span className="font-semibold text-ink whitespace-nowrap">
                                  {project.riskScore.toFixed(
                                    1,
                                  )}
                                  /100
                                </span>
                              )}

                            <RiskBadge
                              risk={project.risk}
                            />
                          </div>
                        ) : (
                          <span className="text-muted">
                            —
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}

                {items.length === 0 && (
                  <tr>
                    <td
                      colSpan={TABLE_COLUMNS.length + 1}
                      className="px-4 py-8 text-center text-sm text-muted"
                    >
                      {/* Role-aware: "0 projects" alone would read as
                          "there is nothing", when the truthful statement
                          is "there is nothing in YOUR jurisdiction". */}
                      {scopeMessage
                        || 'No projects match the selected filters.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && (
          <Pagination
            page={Math.floor(skip / PAGE_SIZE) + 1}
            canGoPrev={skip !== 0}
            canGoNext={items.length >= PAGE_SIZE}
            onPrev={() =>
              setSkip((s) =>
                Math.max(0, s - PAGE_SIZE),
              )
            }
            onNext={() =>
              setSkip((s) => s + PAGE_SIZE)
            }
          />
        )}
      </div>
    </PageContainer>
  )

  if (!authReady) {
    return (
      <div className="min-h-screen flex items-center justify-center gap-2 text-muted">
        <Loader2
          className="animate-spin"
          size={20}
          aria-hidden="true"
        />

        <span className="text-sm">
          Checking your session…
        </span>
      </div>
    )
  }

  if (isAuthenticated) {
    return (
      <AuthenticatedShell title={pageTitleFor('/projects', role, 'Projects')}>
        {content}
      </AuthenticatedShell>
    )
  }

  return (
    <div className="min-h-screen bg-panel">
      <PublicNavbar />

      {content}

      <footer className="border-t border-line bg-white mt-6">
        <div className="max-w-[1200px] mx-auto px-5 py-5 text-xs text-muted flex flex-wrap justify-between gap-3">
          <span>
            © 2026 MPLADS AI Shield -- SIH prototype
          </span>

          <span>
            AI-assisted advisory signals -- not an
            official Government of India portal
          </span>
        </div>
      </footer>
    </div>
  )
}