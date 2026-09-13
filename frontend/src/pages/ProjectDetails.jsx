import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, Download, Loader2 } from 'lucide-react'
import { formatCurrency } from '../lib/formatters'
import { RiskBadge, Section, Disclaimer } from '../components/UI'
import RiskBreakdown from '../components/risk/RiskBreakdown'
import WhyRisky from '../components/risk/WhyRisky'
import { fetchProject, fetchProjectRisk } from '../features/projects/api'
import { API_BASE } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { normalizeRole } from '../lib/roles'
import PageContainer from '../components/layout/PageContainer'

// Phase 5: Project Detail / Project Intelligence.
//
// Visual/product source of truth: mplads-ai-shield.jsx's ProjectDetail
// component. Every field on this page is either a real column from
// GET /projects/:id, a real value from GET /projects/:id/risk, or a
// value mathematically derived from those (utilization %). Nothing here
// is copied from the artifact's mock project data, and no date, name,
// or score is invented when the backend has no value -- those render
// as the em-dash placeholder below instead.
const DASH = '—'

function dash(value) {
  return value === null || value === undefined || value === '' ? DASH : value
}

function fmtMoney(value) {
  return value === null || value === undefined ? DASH : formatCurrency(value)
}

// Plain calendar-date formatting (no timezone/relative logic needed --
// these are all `date` columns on the backend, e.g. sanction_date).
function fmtDate(value) {
  if (!value) return DASH
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return DASH
  return parsed.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

const toNumber = v => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

// Public-facing AI Shield label set. Not reachable today (see the
// role-visibility note near the bottom of this file), but kept so the
// component matches the artifact's full role matrix and is ready if
// /projects/:id is ever made public without more work.
function publicAiLabel(level) {
  const key = (level || '').toUpperCase()
  if (key === 'LOW') return { label: 'NORMAL MONITORING', color: '#1b8a5a', bg: '#e7f4ec' }
  if (key === 'MEDIUM') return { label: 'REQUIRES REVIEW', color: '#b7791f', bg: '#fbf0de' }
  if (key === 'HIGH' || key === 'CRITICAL') return { label: 'HIGH PRIORITY REVIEW', color: '#b4552e', bg: '#fbe7df' }
  return { label: 'NOT YET ASSESSED', color: '#55636e', bg: '#eef1f3' }
}

function LifecycleStep({ label, date, active, last }) {
  return (
    <div className="flex-1 flex flex-col items-start relative min-w-[120px]">
      <div className="flex items-center w-full">
        <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: active ? '#0b2e4f' : '#c7ced5' }} />
        {!last && <div className="flex-1 h-[2px]" style={{ backgroundColor: active ? '#0b2e4f' : '#dce2e8' }} />}
      </div>
      <div className="mt-2">
        <div className="text-xs font-semibold" style={{ color: active ? '#16232e' : '#55636e' }}>{label}</div>
        <div className="text-[11px] text-muted">{date}</div>
      </div>
    </div>
  )
}

const BackLink = () => (
  <Link to="/projects" className="inline-flex items-center gap-1.5 text-sm text-muted mb-4 hover:text-ink">
    <ArrowLeft size={14} /> Back to Project Explorer
  </Link>
)

export default function ProjectDetails() {
  const { id } = useParams()
  const { user } = useAuth()
  // /projects/:id sits behind ProtectedRoute (see app/routes.jsx / App.jsx),
  // so `user` is always present here today -- there is currently no way
  // for an anonymous visitor to reach this page. `role` still falls
  // through to a 'public' branch below for forward-compatibility and to
  // match the artifact's full role matrix, but that branch is not
  // exercised by any real traffic yet. See the final report for what
  // would need to change (a public single-project + public risk
  // endpoint) to actually make this page reachable by anonymous users.
  const role = user ? normalizeRole(user.role) : 'public'

  const [raw, setRaw] = useState(null)
  const [projectLoading, setProjectLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [projectError, setProjectError] = useState(null)

  const [riskResult, setRiskResult] = useState(null)
  const [riskLoading, setRiskLoading] = useState(true)
  const [riskError, setRiskError] = useState(null)

  useEffect(() => {
    let cancelled = false

    setRaw(null)
    setProjectLoading(true)
    setNotFound(false)
    setProjectError(null)
    setRiskResult(null)
    setRiskLoading(true)
    setRiskError(null)

    // Project and risk are fetched independently (not Promise.allSettled)
    // so a slow/failed risk lookup never blocks the project information
    // itself from rendering -- see the "Risk loading" / "Risk
    // unavailable" requirements in the phase brief. id comes back from
    // useParams already URL-decoded by React Router; fetchProject/
    // fetchProjectRisk re-encode it before building the request path so
    // slashes in a real work ID survive as one path segment.
    fetchProject(id)
      .then(project => { if (!cancelled) setRaw(project.raw) })
      .catch(() => { if (!cancelled) setNotFound(true) })
      .finally(() => { if (!cancelled) setProjectLoading(false) })

    fetchProjectRisk(id)
      .then(risk => { if (!cancelled) setRiskResult(risk) })
      .catch(err => { if (!cancelled) setRiskError(err.message || 'Risk information unavailable') })
      .finally(() => { if (!cancelled) setRiskLoading(false) })

    return () => { cancelled = true }
  }, [id])

  if (projectLoading) return (
    <PageContainer maxWidth="1100px">
      <BackLink />
      <div className="card p-14 flex flex-col items-center gap-2 text-muted"><Loader2 className="animate-spin" size={20} /><span className="text-sm">Loading project…</span></div>
    </PageContainer>
  )

  if (notFound) return (
    <PageContainer maxWidth="1100px">
      <BackLink />
      <div className="card p-10 text-center">
        <AlertTriangle className="mx-auto mb-2" size={20} style={{ color: '#b7791f' }} />
        <div className="font-semibold text-[13.5px] text-ink">Project not found</div>
        <p className="text-sm text-muted mt-1">No project with ID <span className="font-mono">{id}</span> exists in the backend.</p>
      </div>
    </PageContainer>
  )

  if (projectError) return (
    <PageContainer maxWidth="1100px">
      <BackLink />
      <div className="card p-10 text-center">
        <AlertTriangle className="mx-auto mb-2" size={20} style={{ color: '#c0392b' }} />
        <div className="font-semibold text-[13.5px]" style={{ color: '#c0392b' }}>Could not load this project</div>
        <p className="text-sm text-muted mt-1">{projectError}</p>
        <p className="text-xs text-muted mt-1">Check that the FastAPI backend is running at {API_BASE}.</p>
      </div>
    </PageContainer>
  )

  // Map the raw ProjectOut record into the fields this page renders.
  // Every value here is a real backend column; nothing is computed or
  // guessed at this stage (utilization is derived further down, from
  // sanctioned/expenditure, per the phase brief's explicit formula).
  const p = {
    id: raw.project_id ?? id,
    state: raw.state ?? null,
    district: raw.district ?? null,
    constituency: raw.constituency ?? null,
    mpName: raw.mp_name ?? null,
    workType: raw.work_type ?? null,
    agency: raw.implementing_agency ?? null,
    sanctioned: toNumber(raw.sanctioned_amount),
    estimatedCost: toNumber(raw.estimated_cost),
    expenditure: toNumber(raw.expenditure),
    financialProgress: toNumber(raw.financial_progress),
    physicalProgress: toNumber(raw.physical_progress),
    sanctionDate: raw.sanction_date ?? null,
    startDate: raw.start_date ?? null,
    expectedCompletion: raw.expected_completion ?? null,
    actualCompletion: raw.actual_completion ?? null,
    status: raw.status ?? null,
    metadata: raw.risk_metadata ?? null,
  }

  // The backend's `projects` table has no recommended_amount,
  // recommended_date, or house (Lok Sabha / Rajya Sabha) column, and no
  // work title distinct from work_type -- see ProjectOut in
  // app/schemas.py. Rather than fabricate any of these, they render as
  // the dash placeholder throughout this page.
  const recommendedAmount = null
  const recommendedDate = null
  const house = null

  // Utilization = expenditure / sanctioned amount x 100, only when
  // sanctioned amount is a valid, non-zero number -- per the phase
  // brief, never computed from a missing/zero denominator. The number
  // shown is the true (possibly >100%, i.e. overspend) figure; only the
  // progress bar's fill width is clamped to 100% so it stays a valid
  // bar, not to hide an overspend signal.
  const utilization = (p.sanctioned && p.sanctioned > 0 && p.expenditure !== null)
    ? (p.expenditure / p.sanctioned) * 100
    : null
  const utilizationBarPct = utilization === null ? 0 : Math.min(100, Math.max(0, utilization))

  const expenditureStarted = p.expenditure !== null && p.expenditure > 0
  // Do NOT infer completion from expenditure or progress -- only a real
  // actual_completion date counts as "Completed" for the lifecycle step.
  const isCompleted = !!p.actualCompletion

  const riskLevel = riskResult?.riskLevel ?? null // already title-cased by normalizeRisk
  const riskLevelKey = (riskLevel || '').toUpperCase()

  // Role visibility, matching the artifact's ProjectDetail component:
  // - ministry/state/district see the numeric AI Shield score
  // - mp sees only the badge (early-warning, no raw score)
  // - public (not reachable today -- see note above) sees generic language only
  // - reasons/evidence are hidden from public entirely
  // - the category-contribution breakdown is ministry-only
  const showScore = role === 'state' || role === 'district' || role === 'ministry'
  const showEvidence = role !== 'public'
  const showModelIntel = role === 'ministry'
  const showActions = role === 'district' || role === 'ministry'

  return (
    <PageContainer maxWidth="1100px">
      <BackLink />

      {/* 2. Project header + 3. AI Shield risk/status card */}
      <div className="flex items-start justify-between flex-wrap gap-4 mb-5">
        <div>
          <div className="eyebrow mb-1">Project Detail · {p.id}</div>
          <h1 className="text-[19px] font-semibold text-ink">{dash(p.workType)}</h1>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[12.5px] text-muted">
            <span>{dash(p.state)} · {dash(p.constituency)}</span>
            <span>MP: {dash(p.mpName)}</span>
            <span>{dash(house)}</span>
            <span>{dash(p.workType)}</span>
          </div>
        </div>

        <div className="card p-3.5 min-w-[220px]">
          {riskLoading ? (
            <div className="flex items-center gap-2 text-muted">
              <Loader2 className="animate-spin" size={14} />
              <span className="text-xs">Loading risk assessment…</span>
            </div>
          ) : riskError ? (
            <div>
              <div className="text-xs text-muted mb-1">AI Shield Status</div>
              <div className="text-[12.5px] font-semibold" style={{ color: '#55636e' }}>Risk information unavailable</div>
            </div>
          ) : showScore ? (
            <>
              <div className="text-xs text-muted mb-1">AI Shield Risk Score</div>
              <div className="text-[26px] font-bold leading-none text-ink">
                {riskResult.riskScore !== null ? riskResult.riskScore.toFixed(1) : DASH}
                <span className="text-[13px] text-muted"> / 100</span>
              </div>
              <div className="mt-2"><RiskBadge risk={riskLevel} /></div>
            </>
          ) : role === 'mp' ? (
            <>
              <div className="text-xs text-muted mb-1">AI Shield Early Warning</div>
              <RiskBadge risk={riskLevel} />
            </>
          ) : (
            (() => {
              const pub = publicAiLabel(riskLevelKey)
              return (
                <>
                  <div className="text-xs text-muted mb-1">AI Shield Status</div>
                  <span className="badge" style={{ color: pub.color, backgroundColor: pub.bg, borderColor: `${pub.color}22` }}>{pub.label}</span>
                </>
              )
            })()
          )}
        </div>
      </div>

      <div className="mb-4"><Disclaimer /></div>

      {/* 4. Financial Overview */}
      <div className="card p-4 mb-4">
        <Section title="Financial Overview" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
          <div><div className="text-xs text-muted">Recommended Amount</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{dash(recommendedAmount)}</div></div>
          <div><div className="text-xs text-muted">Sanctioned Amount</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{fmtMoney(p.sanctioned)}</div></div>
          <div><div className="text-xs text-muted">Expenditure</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{fmtMoney(p.expenditure)}</div></div>
          <div><div className="text-xs text-muted">Utilization</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{utilization === null ? DASH : `${utilization.toFixed(1)}%`}</div></div>
        </div>
        <div className="h-2 rounded-full" style={{ backgroundColor: '#e7ebef' }}>
          <div className="h-2 rounded-full" style={{ width: `${utilizationBarPct}%`, backgroundColor: '#1d63a8' }} />
        </div>
      </div>

      {/* 5. Project Lifecycle */}
      <div className="card p-4 mb-4">
        <Section title="Project Lifecycle" />
        <div className="flex items-start overflow-x-auto pb-1">
          <LifecycleStep label="Recommended" date={dash(recommendedDate)} active={false} />
          <LifecycleStep label="Sanctioned" date={fmtDate(p.sanctionDate)} active={!!p.sanctionDate} />
          <LifecycleStep label="Expenditure Begins" date={expenditureStarted ? fmtDate(p.startDate) : DASH} active={expenditureStarted} />
          <LifecycleStep label="Completed" date={isCompleted ? fmtDate(p.actualCompletion) : DASH} active={isCompleted} last />
        </div>
      </div>

      {/* 6. Financial Progress -- the backend has no historical time
          series for a project (only the current snapshot columns), so
          this is a current sanctioned-vs-expenditure snapshot rather
          than a fabricated trend line, plus the backend's own
          financial/physical progress fields where present. */}
      <div className="card p-4 mb-4">
        <Section title="Financial Progress" subtitle="Current snapshot — historical trend data is not available from the backend" />
        <div className="grid sm:grid-cols-2 gap-4 items-center">
          <div>
            <div className="flex justify-between text-[11.5px] text-muted mb-1">
              <span>Sanctioned</span><span>{fmtMoney(p.sanctioned)}</span>
            </div>
            <div className="h-2.5 rounded-full mb-3" style={{ backgroundColor: '#e7ebef' }}>
              <div className="h-2.5 rounded-full" style={{ width: '100%', backgroundColor: '#b9c7d6' }} />
            </div>
            <div className="flex justify-between text-[11.5px] text-muted mb-1">
              <span>Expenditure</span><span>{fmtMoney(p.expenditure)}</span>
            </div>
            <div className="h-2.5 rounded-full" style={{ backgroundColor: '#e7ebef' }}>
              <div className="h-2.5 rounded-full" style={{ width: `${utilizationBarPct}%`, backgroundColor: '#1d63a8' }} />
            </div>
          </div>
          <div className="text-[12.5px] space-y-1.5">
            <div><span className="text-muted">Financial progress (reported): </span><span className="font-semibold text-ink">{p.financialProgress === null ? DASH : `${p.financialProgress}%`}</span></div>
            <div><span className="text-muted">Physical progress (reported): </span><span className="font-semibold text-ink">{p.physicalProgress === null ? DASH : `${p.physicalProgress}%`}</span></div>
            <div><span className="text-muted">Status: </span><span className="font-semibold text-ink">{dash(p.status)}</span></div>
          </div>
        </div>
      </div>

      {/* 7. Why Is This Flagged? */}
      {showEvidence && (
        <div className="card p-4 mb-4">
          <Section title="Why Is This Flagged?" subtitle="Evidence behind the AI Shield status" />
          {riskLoading ? (
            <div className="flex items-center gap-2 text-muted py-2"><Loader2 className="animate-spin" size={14} /><span className="text-sm">Loading risk evidence…</span></div>
          ) : riskError ? (
            <p className="text-sm text-muted">Risk information unavailable.</p>
          ) : (
            <WhyRisky reasons={riskResult?.reasons || []} evidence={riskResult?.evidence?.signals?.map(s => s.source).filter(Boolean) || []} />
          )}
        </div>
      )}

      {/* 8. Risk Category Contribution (Ministry/Admin only) */}
      {showModelIntel && (
        <div className="card p-4 mb-4">
          <Section title="Risk Category Contribution" subtitle="Fused evidence contributing to the overall AI Shield score" />
          {riskLoading ? (
            <div className="flex items-center gap-2 text-muted py-2"><Loader2 className="animate-spin" size={14} /><span className="text-sm">Loading category contributions…</span></div>
          ) : riskError ? (
            <p className="text-sm text-muted">Category contribution data is not available from the current risk response.</p>
          ) : (
            <RiskBreakdown risk={riskResult} />
          )}
        </div>
      )}

      {/* 9. Project Metadata */}
      <div className="card p-4 mb-4">
        <Section title="Project Metadata" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-[12.5px]">
          <div><span className="text-muted">Source: </span><span className="font-semibold text-ink">{dash(p.metadata?.data_source_flag)}</span></div>
          <div><span className="text-muted">Data quality: </span><span className="font-semibold text-ink">{riskResult?.evidence_status ? riskResult.evidence_status.charAt(0) + riskResult.evidence_status.slice(1).toLowerCase() : DASH}</span></div>
          <div><span className="text-muted">District: </span><span className="font-semibold text-ink">{dash(p.district)}</span></div>
          <div><span className="text-muted">Implementing agency: </span><span className="font-semibold text-ink">{dash(p.agency)}</span></div>
          <div><span className="text-muted">Estimated cost: </span><span className="font-semibold text-ink">{fmtMoney(p.estimatedCost)}</span></div>
          <div><span className="text-muted">Expected completion: </span><span className="font-semibold text-ink">{fmtDate(p.expectedCompletion)}</span></div>
        </div>
      </div>

      {/* 10. Actions -- no backend endpoint exists yet for any of these
          (see the final report), so they render disabled rather than
          faking a successful mutation. */}
      {showActions && (
        <div className="flex gap-2 mt-4">
          <button type="button" disabled className="btn-primary opacity-50 cursor-not-allowed" title="Not available yet — no backend endpoint for this action">Mark for Review</button>
          <button type="button" disabled className="btn-secondary opacity-50 cursor-not-allowed" title="Not available yet — no backend endpoint for this action">Add Note</button>
          <button type="button" disabled className="btn-secondary opacity-50 cursor-not-allowed" title="Not available yet — no backend endpoint for this action"><Download size={13} /> Export Report</button>
        </div>
      )}
    </PageContainer>
  )
}