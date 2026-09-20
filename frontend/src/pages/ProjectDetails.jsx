import React, { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Building2,
  CalendarClock,
  CreditCard,
  Download,
  FileText,
  IndianRupee,
  Layers,
  Loader2,
  Lock,
  Map as MapIcon,
  MapPin,
  Radar,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react'
import { money } from '../data'
import { RiskBadge, Progress, Section, Disclaimer } from '../components/UI'

import RiskFusion from '../components/risk/RiskFusion'
import ComponentFocus from '../components/risk/ComponentFocus'
import PeerComparison from '../components/risk/PeerComparison'
import RecommendedReview from '../components/risk/RecommendedReview'
import DataQualityPanel from '../components/risk/DataQualityPanel'
import WhyRisky from '../components/risk/WhyRisky'
import RiskLevelBanner from '../components/risk/RiskLevelBanner'
import RiskCharts from '../components/risk/RiskCharts'
import { buildRiskModel, statusTone } from '../lib/riskModel'

import { downloadProjectReport } from '../features/reports/api'
import {
  fetchProject,
  fetchProjectRisk,
  fetchPublicProject,
  fetchDemoProject,
  fetchDemoProjectRisk,
} from '../features/projects/api'
import { API_BASE } from '../lib/api'
import { formatDate } from '../lib/formatters'
import PageContainer from '../components/layout/PageContainer'
import AuthenticatedShell from '../components/layout/AuthenticatedShell'
import PublicNavbar from '../components/layout/PublicNavbar'
import { useAuth } from '../context/AuthContext'

/* ==========================================================================
   PROJECT DETAILS
   ==========================================================================
   Information hierarchy (brief section 17), delivered as tabs so a reviewer
   can go straight to the domain they care about without losing the whole
   explanation:

     Overview     -> what is this project, and what is its overall risk
     Risk Fusion  -> the complete explanation: breakdown AND why flagged
     Financials / Timeline / Payments / Compliance / Duplicates / AI Insights
                  -> one detection domain each, in full
     Map          -> where the work is recorded

   The risk data comes from ONE request (GET /projects/:id/risk) that already
   carries every component, its evidence and its data-quality status, so
   switching tabs issues no further calls.

   Visitor types are unchanged from before:
     anonymous -> /public/projects/:id            (no risk intelligence)
     demo      -> /demo/projects/:id  + /risk     (no JWT required)
     official  -> /projects/:id       + /risk
   ========================================================================== */

function LifecycleStep({ label, date, active, last }) {
  return (
    <div className="flex-1 flex flex-col items-start relative min-w-[110px]">
      <div className="flex items-center w-full">
        <div
          className="w-3 h-3 rounded-full shrink-0"
          style={{ backgroundColor: active ? '#0b2e4f' : '#c7ced5' }}
        />
        {!last && (
          <div
            className="flex-1 h-[2px]"
            style={{ backgroundColor: active ? '#0b2e4f' : '#dce2e8' }}
          />
        )}
      </div>

      <div className="mt-2">
        <div className="text-xs font-semibold" style={{ color: active ? '#16232e' : '#55636e' }}>
          {label}
        </div>
        <div className="text-[11px] text-muted">{date}</div>
      </div>
    </div>
  )
}

const titleCase = s => (s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : null)

const toNumber = v => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function renderMetadata(meta) {
  if (meta === null || meta === undefined || meta === '') return null

  let obj = meta

  if (typeof meta === 'string') {
    try {
      obj = JSON.parse(meta)
    } catch {
      return <p className="text-sm text-ink whitespace-pre-wrap">{meta}</p>
    }
  }

  if (typeof obj === 'object' && obj !== null) {
    const entries = Object.entries(obj)
    if (entries.length === 0) return null

    return (
      <div className="grid sm:grid-cols-2 gap-3">
        {entries.map(([k, v]) => (
          <div key={k} className="text-sm">
            <span className="text-muted">{k}: </span>
            <span className="font-semibold text-ink">
              {v === null || v === undefined || v === '' ? 'Not available' : String(v)}
            </span>
          </div>
        ))}
      </div>
    )
  }

  return <p className="text-sm text-ink">{String(obj)}</p>
}

const BackLink = () => (
  <Link
    to="/projects"
    className="inline-flex items-center gap-1.5 text-sm text-muted mb-4 hover:text-ink"
  >
    <ArrowLeft size={14} />
    Back to projects
  </Link>
)

// Tab definitions. `risk` marks tabs that require risk intelligence and are
// therefore hidden from anonymous visitors, who never receive that payload.
const TABS = [
  { id: 'overview', label: 'Overview', icon: FileText, risk: false },
  { id: 'risk', label: 'Risk Fusion', icon: Activity, risk: true },
  { id: 'financials', label: 'Financials', icon: IndianRupee, risk: false },
  { id: 'timeline', label: 'Timeline', icon: CalendarClock, risk: false },
  { id: 'payments', label: 'Payments', icon: CreditCard, risk: true },
  { id: 'compliance', label: 'Compliance', icon: ShieldCheck, risk: true },
  { id: 'duplicates', label: 'Duplicates', icon: Layers, risk: true },
  { id: 'ai', label: 'AI Insights', icon: Radar, risk: true },
  { id: 'map', label: 'Map', icon: MapIcon, risk: false },
]

function TabNav({ tabs, active, onChange }) {
  return (
    <div className="card mb-4 overflow-x-auto">
      <div role="tablist" aria-label="Project sections" className="flex min-w-max">
        {tabs.map(tab => {
          const Icon = tab.icon
          const selected = tab.id === active
          return (
            <button
              key={tab.id}
              role="tab"
              type="button"
              id={`tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`panel-${tab.id}`}
              onClick={() => onChange(tab.id)}
              className={`inline-flex items-center gap-2 px-4 py-3 text-[12.5px] whitespace-nowrap border-b-2 transition-colors focus:outline-none focus:ring-2 focus:ring-navy/30 ${
                selected
                  ? 'border-navy text-navy font-semibold'
                  : 'border-transparent text-muted hover:text-ink'
              }`}
            >
              <Icon size={15} aria-hidden="true" />
              {tab.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function Card({ children, className = '' }) {
  return <div className={`card p-4 ${className}`}>{children}</div>
}

/** Small "this domain contributed X" strip shown at the top of a domain tab. */
function DomainRiskSummary({ model, name }) {
  const component = model?.components?.find(item => item.name === name)
  if (!component) return null
  const tone = statusTone(component.status)

  return (
    <div
      className="rounded-md border px-3.5 py-2.5 mb-4 flex flex-wrap items-center justify-between gap-3"
      style={{ borderColor: `${tone.color}33`, backgroundColor: `${tone.bg}55` }}
    >
      <span className="text-[12.5px] text-ink">
        {component.triggered
          ? `${component.label} contributed ${component.contribution.toFixed(2)} of the ${
              model.score === null ? '—' : model.score.toFixed(1)
            } point risk score.`
          : `${component.label} was evaluated and contributed no points to the risk score.`}
      </span>
      <span
        className="text-[11px] font-semibold tabular-nums"
        style={{ color: tone.color }}
      >
        {component.sharePct.toFixed(1)}% of final risk
      </span>
    </div>
  )
}

export default function ProjectDetails() {
  const { id } = useParams()
  const { status, isAuthenticated, isDemo } = useAuth()

  const authReady = status !== 'checking'

  // Real authenticated users and demo users both receive the full experience.
  const showRiskIntelligence = isAuthenticated || isDemo

  // Report export requires a real authenticated JWT; demo sessions cannot use
  // the protected reports API.
  const useProtectedApi = isAuthenticated && !isDemo

  const [raw, setRaw] = useState(null)
  const [riskResult, setRiskResult] = useState(null)
  const [riskError, setRiskError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => {
    if (!authReady) return

    let cancelled = false

    setLoading(true)
    setError(null)
    setRiskError(null)
    setNotFound(false)
    setRaw(null)
    setRiskResult(null)

    const applyPair = ([project, risk]) => {
      if (cancelled) return

      if (project.status === 'rejected') {
        const message = project.reason?.message || ''
        if (/\b404\b/.test(message)) {
          setNotFound(true)
        } else {
          setError(message || 'Failed to load project')
        }
        return
      }

      setRaw(project.value.raw)

      if (risk.status === 'fulfilled') {
        setRiskResult(risk.value)
      } else {
        setRiskError(risk.reason?.message || 'Failed to load Risk Fusion data')
      }
    }

    // Demo has no JWT, so it uses the dedicated /demo endpoints.
    if (isDemo) {
      Promise.allSettled([fetchDemoProject(id), fetchDemoProjectRisk(id)])
        .then(applyPair)
        .catch(err => {
          if (!cancelled) setError(err.message || 'Failed to reach the API')
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })

      return () => {
        cancelled = true
      }
    }

    if (isAuthenticated) {
      Promise.allSettled([fetchProject(id), fetchProjectRisk(id)])
        .then(applyPair)
        .catch(err => {
          if (!cancelled) setError(err.message || 'Failed to reach the API')
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })

      return () => {
        cancelled = true
      }
    }

    // Anonymous public visitors intentionally receive NO Risk Fusion data.
    fetchPublicProject(id)
      .then(project => {
        if (!cancelled) setRaw(project.raw)
      })
      .catch(err => {
        if (cancelled) return
        if (/\b404\b/.test(err.message || '')) {
          setNotFound(true)
        } else {
          setError(err.message || 'Failed to reach the API')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [id, authReady, isAuthenticated, isDemo])

  // One model, built once per risk payload, shared by every tab. Switching
  // tabs therefore never re-fetches and never re-derives anything.
  const riskModel = useMemo(() => buildRiskModel(riskResult), [riskResult])

  async function handleExportReport() {
    setExporting(true)
    setExportError(null)
    try {
      await downloadProjectReport(id)
    } catch (err) {
      setExportError(err.message || 'Report generation failed. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  function withChrome(node) {
    if (!authReady) {
      return (
        <div className="min-h-screen flex items-center justify-center gap-2 text-muted">
          <Loader2 className="animate-spin" size={20} aria-hidden="true" />
          <span className="text-sm">Checking your session…</span>
        </div>
      )
    }

    if (isAuthenticated || isDemo) {
      return <AuthenticatedShell title="Project Intelligence">{node}</AuthenticatedShell>
    }

    return (
      <div className="min-h-screen bg-panel">
        <PublicNavbar />
        {node}
        <footer className="border-t border-line bg-white mt-6">
          <div className="max-w-[1200px] mx-auto px-5 py-5 text-xs text-muted flex flex-wrap justify-between gap-3">
            <span>© 2026 MPLADS AI Shield -- SIH prototype</span>
            <span>
              AI-assisted advisory signals -- not an official Government of India portal
            </span>
          </div>
        </footer>
      </div>
    )
  }

  if (loading) {
    return withChrome(
      <PageContainer maxWidth="1320px">
        <BackLink />
        <div className="card p-14 flex flex-col items-center gap-2 text-muted">
          <Loader2 className="animate-spin" size={20} />
          <span className="text-sm">Loading project…</span>
        </div>
      </PageContainer>
    )
  }

  if (notFound) {
    return withChrome(
      <PageContainer maxWidth="1320px">
        <BackLink />
        <div className="card p-10 text-center">
          <AlertTriangle className="mx-auto mb-2" size={20} style={{ color: '#b7791f' }} />
          <div className="font-semibold text-[13.5px] text-ink">Project not found</div>
          <p className="text-sm text-muted mt-1">
            No project with ID <span className="font-mono">{id}</span> exists in the backend.
          </p>
        </div>
      </PageContainer>
    )
  }

  if (error) {
    return withChrome(
      <PageContainer maxWidth="1320px">
        <BackLink />
        <div className="card p-10 text-center">
          <AlertTriangle className="mx-auto mb-2" size={20} style={{ color: '#c0392b' }} />
          <div className="font-semibold text-[13.5px]" style={{ color: '#c0392b' }}>
            Could not load this project
          </div>
          <p className="text-sm text-muted mt-1">{error}</p>
          <p className="text-xs text-muted mt-1">
            Check that the FastAPI backend is running at {API_BASE}.
          </p>
        </div>
      </PageContainer>
    )
  }

  const p = {
    id: raw.project_id ?? id,
    state: raw.state ?? null,
    district: raw.district ?? null,
    constituency: raw.constituency ?? null,
    mpName: raw.mp_name ?? null,
    workType: raw.work_type ?? null,
    agency: raw.implementing_agency ?? null,
    sanctioned: toNumber(raw.sanctioned_amount),
    expenditure: toNumber(raw.expenditure),
    status: raw.status ?? null,
    sanctionDate: raw.sanction_date ?? null,
    startDate: raw.start_date ?? null,
    expectedCompletion: raw.expected_completion ?? null,
    actualCompletion: raw.actual_completion ?? null,
    riskScore: riskResult?.riskScore ?? toNumber(raw.risk_score),
    risk: riskResult?.riskLevel ?? titleCase(raw.risk_level),
    maxSimilarity: toNumber(raw.raw_max_similarity),
    similarWorkId: raw.most_similar_work_id ?? null,
    // Legacy flat reasons, preserved as a last-resort fallback so the WHY
    // information can never vanish entirely.
    reasons: riskResult?.reasons?.length
      ? riskResult.reasons
      : [raw.risk_reason_1, raw.risk_reason_2, raw.risk_reason_3].filter(Boolean),
    metadata: raw.risk_metadata ?? null,
  }

  const financialPct =
    p.sanctioned && p.expenditure !== null
      ? Math.min(100, Math.round((p.expenditure / p.sanctioned) * 100))
      : null

  const remaining =
    p.sanctioned !== null && p.expenditure !== null ? p.sanctioned - p.expenditure : null

  const tabs = TABS.filter(tab => showRiskIntelligence || !tab.risk)
  const currentTab = tabs.some(tab => tab.id === activeTab) ? activeTab : 'overview'

  const riskUnavailable = showRiskIntelligence && !riskModel

  // ================================================================
  // Tab panels
  // ================================================================

  const financialOverview = (
    <Card>
      <Section title="Financial Overview" subtitle="As recorded in the canonical project dataset" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
        <div>
          <div className="text-xs text-muted">Sanctioned</div>
          <div className="text-[16px] font-semibold mt-0.5 text-ink">
            {p.sanctioned !== null ? money(p.sanctioned) : 'Not available'}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Expenditure</div>
          <div className="text-[16px] font-semibold mt-0.5 text-ink">
            {p.expenditure !== null ? money(p.expenditure) : 'Not available'}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Remaining</div>
          <div className="text-[16px] font-semibold mt-0.5 text-ink">
            {remaining !== null ? money(remaining) : 'Not available'}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Financial progress</div>
          <div className="text-[16px] font-semibold mt-0.5 text-ink">
            {financialPct !== null ? `${financialPct}%` : 'Not available'}
          </div>
        </div>
      </div>
      {financialPct !== null && <Progress value={financialPct} />}
    </Card>
  )

  const lifecycleCard = (
    <Card>
      <Section
        title="Project Lifecycle"
        subtitle="Recommendation/sanction/completion dates as recorded by the backend"
      />
      <div className="flex items-start overflow-x-auto pb-1">
        <LifecycleStep
          label="Sanctioned"
          date={formatDate(p.sanctionDate)}
          active={!!p.sanctionDate}
        />
        <LifecycleStep label="Work Started" date={formatDate(p.startDate)} active={!!p.startDate} />
        <LifecycleStep
          label="Expected Completion"
          date={formatDate(p.expectedCompletion)}
          active={!!p.expectedCompletion}
        />
        <LifecycleStep
          label="Completed"
          date={formatDate(p.actualCompletion)}
          active={!!p.actualCompletion}
          last
        />
      </div>
    </Card>
  )

  const similarityCard = (
    <Card>
      <Section title="Similarity Check" subtitle="Closest matching work order, if any" />
      {p.similarWorkId || p.maxSimilarity !== null ? (
        <div className="grid sm:grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-muted text-xs">Most similar work ID</div>
            <div className="font-semibold mt-1 text-ink break-all">
              {p.similarWorkId || 'Not available'}
            </div>
          </div>
          <div>
            <div className="text-muted text-xs">Similarity score</div>
            <div className="font-semibold mt-1 text-ink">
              {p.maxSimilarity !== null ? p.maxSimilarity.toFixed(3) : 'Not available'}
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted">No similarity data recorded for this project.</p>
      )}
    </Card>
  )

  function domainTab(name, title, extraCards = []) {
    if (!riskModel) {
      return (
        <Card>
          <Section title={title} />
          <p className="text-sm text-muted">
            {riskError || 'Risk analysis is unavailable for this project.'}
          </p>
        </Card>
      )
    }

    return (
      <div className="space-y-4">
        {extraCards}
        <Card>
          <Section title={title} />
          <DomainRiskSummary model={riskModel} name={name} />
          <ComponentFocus model={riskModel} name={name} title={title} />
        </Card>
      </div>
    )
  }

  function renderTab() {
    switch (currentTab) {
      case 'risk':
        return <RiskFusion risk={riskResult} error={riskError} />

      case 'financials':
        return domainTab('financial_anomaly', 'Financial Anomaly Risk', [
          <React.Fragment key="fin">{financialOverview}</React.Fragment>,
        ])

      case 'timeline':
        return domainTab('timeline_anomaly', 'Timeline Anomaly Risk', [
          <React.Fragment key="life">{lifecycleCard}</React.Fragment>,
        ])

      case 'payments':
        return domainTab('payment', 'Payment Pattern Risk')

      case 'compliance':
        return (
          <div className="space-y-4">
            <Card>
              <Section title="Compliance Risk" />
              <DomainRiskSummary model={riskModel} name="compliance" />
              <ComponentFocus model={riskModel} name="compliance" title="Compliance Risk" />
            </Card>
            <Card>
              <Section
                title="Data Quality Risk"
                subtitle="Source/field conflicts are scored separately so they never double-count against compliance"
              />
              <ComponentFocus model={riskModel} name="data_quality" title="Data Quality Risk" />
            </Card>
            {riskModel && (
              <Card>
                <DataQualityPanel model={riskModel} />
              </Card>
            )}
          </div>
        )

      case 'duplicates':
        return domainTab('duplicate', 'Duplicate / Similar Work Risk', [
          <React.Fragment key="sim">{similarityCard}</React.Fragment>,
        ])

      case 'ai':
        return (
          <div className="space-y-4">
            <Card>
              <Section
                title="ML Anomaly Risk"
                subtitle="Unsupervised multivariate outlier detection over the engineered feature set"
              />
              <DomainRiskSummary model={riskModel} name="isolation_forest" />
              <ComponentFocus
                model={riskModel}
                name="isolation_forest"
                title="ML Anomaly Risk"
              />
            </Card>

            {riskModel && <RiskCharts model={riskModel} />}

            {riskModel && (
              <div className="grid xl:grid-cols-2 gap-4 items-start">
                <Card>
                  <PeerComparison model={riskModel} />
                </Card>
                <Card>
                  <RecommendedReview model={riskModel} />
                </Card>
              </div>
            )}

            {p.metadata !== null && (
              <Card>
                <Section title="Risk Metadata" subtitle="Additional context supplied by the model" />
                {renderMetadata(p.metadata) || (
                  <p className="text-sm text-muted">No additional metadata recorded.</p>
                )}
              </Card>
            )}
          </div>
        )

      case 'map':
        return (
          <Card>
            <Section title="Location" subtitle="Location fields recorded for this work" />
            <dl className="grid sm:grid-cols-2 gap-4 text-sm">
              {[
                ['State', p.state],
                ['District', p.district],
                ['Constituency', p.constituency],
                ['Implementing agency', p.agency],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-muted text-xs">{label}</dt>
                  <dd className="font-semibold mt-1 text-ink">{value || 'Not available'}</dd>
                </div>
              ))}
            </dl>
            <Link
              to="/map"
              className="inline-flex items-center gap-1.5 mt-4 text-sm font-semibold text-navy hover:underline"
            >
              <MapIcon size={14} />
              Open the national map
            </Link>
          </Card>
        )

      case 'overview':
      default:
        return (
          <div className="space-y-4">
            {financialOverview}
            {lifecycleCard}

            {showRiskIntelligence && (
              <div className="grid xl:grid-cols-3 gap-4 items-start">
                <Card className="xl:col-span-2">
                  <Section
                    title="Why This Project Was Flagged"
                    subtitle="Summary of the detected risk signals — open the Risk Fusion tab for the full explanation"
                  />

                  {riskModel && riskModel.triggered.length > 0 ? (
                    <>
                      <ul className="space-y-2">
                        {riskModel.triggered.map(component => {
                          const tone = statusTone(component.status)
                          return (
                            <li
                              key={component.name}
                              className="rounded-md border border-line px-3.5 py-2.5"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <span className="text-[12.5px] font-semibold text-ink">
                                  {component.label}
                                </span>
                                <span
                                  className="text-[11px] font-semibold tabular-nums"
                                  style={{ color: tone.color }}
                                >
                                  {component.contribution.toFixed(1)} pts ·{' '}
                                  {component.sharePct.toFixed(1)}%
                                </span>
                              </div>
                              {component.reasons[0] && (
                                <p className="text-[12px] text-muted leading-5 mt-1">
                                  {component.reasons[0]}
                                </p>
                              )}
                            </li>
                          )
                        })}
                      </ul>

                      <button
                        type="button"
                        onClick={() => setActiveTab('risk')}
                        className="mt-3 text-sm font-semibold text-navy hover:underline"
                      >
                        See the full risk explanation →
                      </button>
                    </>
                  ) : riskModel ? (
                    <p className="text-sm text-muted">
                      No risk signal triggered for this project across the components that could be
                      evaluated.
                    </p>
                  ) : (
                    // Last-resort fallback: if the structured risk payload is
                    // unavailable, show whatever reason text the project record
                    // itself carries rather than nothing at all.
                    <WhyRisky reasons={p.reasons} />
                  )}
                </Card>

                <Card>
                  <div className="flex items-center gap-2 font-semibold text-[13.5px] text-ink">
                    <Sparkles style={{ color: '#0b2e4f' }} size={16} />
                    AI Risk Intelligence
                  </div>
                  <p className="text-xs text-muted mt-1">
                    Advisory signal · human verification required
                  </p>

                  <div className="mt-5 flex items-end justify-between">
                    <div>
                      <div className="text-[28px] font-bold leading-none text-ink tabular-nums">
                        {p.riskScore !== null ? p.riskScore.toFixed(1) : '—'}
                      </div>
                      <div className="text-xs text-muted mt-1">risk score / 100</div>
                    </div>
                    <RiskBadge risk={p.risk} />
                  </div>

                  <div className="mt-3">
                    <Progress
                      value={
                        p.riskScore !== null ? Math.min(100, Math.max(0, p.riskScore)) : null
                      }
                    />
                  </div>

                  {riskModel && (
                    <dl className="mt-4 space-y-2 text-[12px]">
                      <div className="flex justify-between gap-3">
                        <dt className="text-muted">Active risk signals</dt>
                        <dd className="text-ink font-semibold">{riskModel.triggered.length}</dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-muted">Evidence status</dt>
                        <dd className="text-ink font-semibold">
                          {riskModel.evidenceStatus || 'Not recorded'}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt className="text-muted">Highest contributor</dt>
                        <dd className="text-ink font-semibold text-right">
                          {riskModel.triggered[0]?.label || 'None'}
                        </dd>
                      </div>
                    </dl>
                  )}

                  <div className="mt-5">
                    <Disclaimer compact />
                  </div>
                </Card>
              </div>
            )}

            {similarityCard}
          </div>
        )
    }
  }

  // ================================================================
  // Render
  // ================================================================

  return withChrome(
    <PageContainer maxWidth="1320px">
      <BackLink />

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4 mb-4">
        <div className="min-w-0">
          <div className="eyebrow mb-1 font-mono text-[11.5px] text-muted break-all">{p.id}</div>

          <h1 className="text-[20px] font-semibold text-ink">{p.workType || 'Untitled work'}</h1>

          <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2 text-[12.5px] text-muted">
            <span className="inline-flex gap-1.5 items-center">
              <MapPin size={13} />
              {p.district || 'Not available'}, {p.state || 'Not available'}
            </span>
            <span className="inline-flex gap-1.5 items-center">
              <Users size={13} />
              {p.constituency || 'Not available'}
              {p.mpName ? ` · ${p.mpName}` : ''}
            </span>
            <span className="inline-flex gap-1.5 items-center">
              <Building2 size={13} />
              {p.agency || 'Not available'}
            </span>
          </div>

          {useProtectedApi && (
            <div className="mt-3">
              <button
                onClick={handleExportReport}
                disabled={exporting}
                className="btn-secondary disabled:opacity-50"
              >
                {exporting ? (
                  <Loader2 className="animate-spin" size={15} />
                ) : (
                  <Download size={15} />
                )}{' '}
                Export Report
              </button>
              {exportError && (
                <p className="text-xs mt-1.5" style={{ color: '#c0392b' }}>
                  {exportError}
                </p>
              )}
            </div>
          )}
        </div>

        {showRiskIntelligence ? (
          <div className="flex items-center gap-3">
            <RiskBadge risk={p.risk} />
            <div className="card px-4 py-2.5 text-right">
              <div className="text-[11px] text-muted">Risk score</div>
              <div className="text-[20px] font-bold leading-tight text-ink tabular-nums">
                {p.riskScore !== null ? p.riskScore.toFixed(1) : '—'}
                <span className="text-[12px] font-normal text-muted"> / 100</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="card p-3.5 min-w-[200px] flex items-start gap-2">
            <Lock size={14} className="text-muted mt-0.5 shrink-0" />
            <div>
              <div className="text-xs font-semibold text-ink">AI Shield Risk Score</div>
              <p className="text-[11px] text-muted mt-0.5">
                Sign in to view the AI Shield risk assessment for this project.
              </p>
            </div>
          </div>
        )}
      </div>

      {showRiskIntelligence && (
        <RiskLevelBanner
          level={riskModel?.level || p.risk}
          score={riskModel?.score ?? p.riskScore}
          model={riskModel}
        />
      )}

      <div className="mb-4">
        <Disclaimer />
      </div>

      <TabNav tabs={tabs} active={currentTab} onChange={setActiveTab} />

      {riskUnavailable && riskError && currentTab !== 'risk' && (
        <div className="rounded-md border border-line bg-warn-bg/50 px-3.5 py-2.5 mb-4 flex items-start gap-2">
          <AlertTriangle size={15} style={{ color: '#b7791f' }} className="mt-0.5 shrink-0" />
          <p className="text-[12px] text-ink leading-4">
            Risk analysis could not be loaded for this project. Project information below is
            unaffected. {riskError}
          </p>
        </div>
      )}

      <div role="tabpanel" id={`panel-${currentTab}`} aria-labelledby={`tab-${currentTab}`}>
        {renderTab()}
      </div>

      {!showRiskIntelligence && (
        <div className="card p-6 text-center mt-4">
          <Lock className="mx-auto mb-2" size={18} style={{ color: '#0b2e4f' }} />
          <div className="font-semibold text-[13.5px] text-ink">
            AI Shield risk intelligence is only available to signed-in users
          </div>
          <p className="text-sm text-muted mt-1">
            Risk scoring, flagged reasons, category breakdown, and similarity checks require an
            authenticated Ministry/Admin or scoped session.
          </p>
          <Link
            to="/login"
            className="inline-block mt-3 text-sm font-semibold text-navy hover:underline"
          >
            Sign in
          </Link>
        </div>
      )}
    </PageContainer>
  )
}