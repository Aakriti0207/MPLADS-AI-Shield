import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowLeft, Building2, IndianRupee, Loader2, MapPin, ShieldAlert, Sparkles, Users } from 'lucide-react'
import { money } from '../data'
import { RiskBadge, Progress, Section, Disclaimer } from '../components/UI'
import RiskBreakdown from '../components/risk/RiskBreakdown'
import WhyRisky from '../components/risk/WhyRisky'

import { fetchProject, fetchProjectRisk } from '../features/projects/api'
import { API_BASE } from '../lib/api'
import { placeholderLifecycleDates } from '../lib/mockData'
import PageContainer from '../components/layout/PageContainer'

function LifecycleStep({ label, date, active, last }) {
  return (
    <div className="flex-1 flex flex-col items-start relative min-w-[110px]">
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

const titleCase = s => s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : null

const toNumber = v => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function renderMetadata(meta) {
  if (meta === null || meta === undefined || meta === '') return null
  let obj = meta
  if (typeof meta === 'string') {
    try { obj = JSON.parse(meta) } catch { return <p className="text-sm text-ink whitespace-pre-wrap">{meta}</p> }
  }
  if (typeof obj === 'object') {
    const entries = Object.entries(obj)
    if (entries.length === 0) return null
    return (
      <div className="grid sm:grid-cols-2 gap-3">
        {entries.map(([k, v]) => (
          <div key={k} className="text-sm"><span className="text-muted">{k}: </span><span className="font-semibold text-ink">{v === null || v === undefined || v === '' ? 'Not available' : String(v)}</span></div>
        ))}
      </div>
    )
  }
  return <p className="text-sm text-ink">{String(obj)}</p>
}

const BackLink = () => <Link to="/projects" className="inline-flex items-center gap-1.5 text-sm text-muted mb-4 hover:text-ink"><ArrowLeft size={14} /> Back to projects</Link>

export default function ProjectDetails() {
  const { id } = useParams()
  const [raw, setRaw] = useState(null)
  const [riskResult, setRiskResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setNotFound(false)
    // id comes back from useParams already URL-decoded by React Router, so
    // a real project_id like "WS/MP001/2023-2024/103702" is a plain string
    // here; fetchProject/fetchProjectRisk re-encode it before building the
    // request path so the slashes survive as one path segment.
    Promise.allSettled([fetchProject(id), fetchProjectRisk(id)])
      .then(([project, risk]) => {
        if (cancelled) return
        if (project.status === 'rejected') { setNotFound(true); return }
        setRaw(project.value.raw)
        if (risk.status === 'fulfilled') setRiskResult(risk.value)
      })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id])

  if (loading) return (
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

  if (error) return (
    <PageContainer maxWidth="1100px">
      <BackLink />
      <div className="card p-10 text-center">
        <AlertTriangle className="mx-auto mb-2" size={20} style={{ color: '#c0392b' }} />
        <div className="font-semibold text-[13.5px]" style={{ color: '#c0392b' }}>Could not load this project</div>
        <p className="text-sm text-muted mt-1">{error}</p>
        <p className="text-xs text-muted mt-1">Check that the FastAPI backend is running at {API_BASE}.</p>
      </div>
    </PageContainer>
  )

  // Map the raw API record into the fields this page renders.
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
    riskScore: riskResult?.riskScore ?? toNumber(raw.risk_score),
    risk: riskResult?.riskLevel ?? titleCase(raw.risk_level),
    maxSimilarity: toNumber(raw.raw_max_similarity),
    similarWorkId: raw.most_similar_work_id ?? null,
    reasons: riskResult?.reasons?.length ? riskResult.reasons : [raw.risk_reason_1, raw.risk_reason_2, raw.risk_reason_3].filter(Boolean),
    metadata: raw.risk_metadata ?? null,
  }

  const financialPct = (p.sanctioned && p.expenditure !== null) ? Math.min(100, Math.round((p.expenditure / p.sanctioned) * 100)) : null
  const riskGaugePct = p.riskScore !== null ? Math.min(100, Math.max(0, p.riskScore)) : null

  return (
    <PageContainer maxWidth="1100px">
      <BackLink />

      <div className="flex items-start justify-between flex-wrap gap-4 mb-5">
        <div>
          <div className="eyebrow mb-1">{p.id}{p.workType ? ` · ${p.workType}` : ''}</div>
          <h1 className="text-[19px] font-semibold text-ink">{p.workType || 'Untitled work'}</h1>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2 text-[12.5px] text-muted">
            <span className="inline-flex gap-1.5 items-center"><MapPin size={13} />{p.district || 'Not available'}, {p.state || 'Not available'}</span>
            <span className="inline-flex gap-1.5 items-center"><Users size={13} />{p.constituency || 'Not available'}{p.mpName ? ` · ${p.mpName}` : ''}</span>
            <span className="inline-flex gap-1.5 items-center"><Building2 size={13} />{p.agency || 'Not available'}</span>
          </div>
        </div>
        <div className="card p-3.5 min-w-[200px]">
          <div className="text-xs text-muted mb-1">AI Shield Risk Score</div>
          <div className="text-[24px] font-bold leading-none text-ink">{p.riskScore !== null ? p.riskScore.toFixed(1) : '—'}<span className="text-[13px] text-muted"> / 100</span></div>
          <div className="mt-2"><RiskBadge risk={p.risk} /></div>
        </div>
      </div>

      <div className="mb-4"><Disclaimer /></div>

      <div className="card p-4 mb-4">
        <Section title="Financial Overview" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-1">
          <div><div className="text-xs text-muted">Sanctioned</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{p.sanctioned !== null ? money(p.sanctioned) : 'Not available'}</div></div>
          <div><div className="text-xs text-muted">Expenditure</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{p.expenditure !== null ? money(p.expenditure) : 'Not available'}</div></div>
          <div><div className="text-xs text-muted">Financial progress</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{financialPct !== null ? `${financialPct}%` : 'Not available'}</div></div>
          <div><div className="text-xs text-muted">Risk score</div><div className="text-[16px] font-semibold mt-0.5 text-ink">{p.riskScore !== null ? `${p.riskScore.toFixed(1)} / 100` : 'Not available'}</div></div>
        </div>
        {financialPct !== null && <Progress value={financialPct} />}
      </div>

      <div className="card p-4 mb-4">
        <Section title="Project Lifecycle" subtitle="Illustrative dates — pending recommendation/sanction/completion date fields from the backend" />
        <div className="flex items-start overflow-x-auto pb-1">
          {(() => {
            const dates = placeholderLifecycleDates(p.id)
            const expenditureStarted = p.expenditure !== null && p.expenditure > 0
            const completed = p.status === 'Completed'
            return (
              <>
                <LifecycleStep label="Recommended" date={dates.recommended} active />
                <LifecycleStep label="Sanctioned" date={dates.sanctioned} active={p.sanctioned !== null} />
                <LifecycleStep label="Expenditure Begins" date={expenditureStarted ? dates.expenditureBegins : 'Pending'} active={expenditureStarted} />
                <LifecycleStep label="Completed" date={completed ? dates.completed : 'Pending'} active={completed} last />
              </>
            )
          })()}
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">

          <div className="card p-4">
            <Section title="Why Is This Flagged?" subtitle="Evidence behind the AI Shield status" />
            <WhyRisky reasons={p.reasons} evidence={riskResult?.evidence?.signals || []} />
          </div>

          <div className="card p-4">
            <Section title="Risk Category Contribution" subtitle="Individual signals behind the overall risk score" />
            <RiskBreakdown risk={raw} />
          </div>

          <div className="card p-4">
            <Section title="Similarity Check" subtitle="Closest matching work order, if any" />
            {p.similarWorkId || p.maxSimilarity !== null ? (
              <div className="grid sm:grid-cols-2 gap-4 text-sm">
                <div><div className="text-muted text-xs">Most similar work ID</div><div className="font-semibold mt-1 text-ink">{p.similarWorkId || 'Not available'}</div></div>
                <div><div className="text-muted text-xs">Similarity score</div><div className="font-semibold mt-1 text-ink">{p.maxSimilarity !== null ? p.maxSimilarity.toFixed(3) : 'Not available'}</div></div>
              </div>
            ) : <p className="text-sm text-muted">No similarity data recorded for this project.</p>}
          </div>

          {p.metadata !== null && (
            <div className="card p-4">
              <Section title="Risk Metadata" subtitle="Additional context supplied by the model" />
              {renderMetadata(p.metadata) || <p className="text-sm text-muted">No additional metadata recorded.</p>}
            </div>
          )}

        </div>

        <div className="card p-4 h-fit">
          <div className="flex items-center gap-2 font-semibold text-[13.5px] text-ink"><Sparkles style={{ color: '#0b2e4f' }} size={16} /> AI Risk Intelligence</div>
          <p className="text-xs text-muted mt-1">Advisory signal · human verification required</p>
          <div className="mt-5 flex items-end justify-between">
            <div><div className="text-[28px] font-bold leading-none text-ink">{p.riskScore !== null ? p.riskScore.toFixed(1) : '—'}</div><div className="text-xs text-muted mt-1">risk score / 100</div></div>
            <RiskBadge risk={p.risk} />
          </div>
          <div className="mt-3"><Progress value={riskGaugePct} /></div>
          <div className="mt-5 space-y-3 text-[12.5px]">
            <div className="flex gap-2"><ShieldAlert size={15} style={{ color: '#c0392b' }} className="shrink-0 mt-0.5" /><span className="text-ink">
              {p.risk === 'Critical' ? 'Multiple strong risk signals were detected — prioritize immediate human review.'
                : p.risk === 'High' ? 'Several risk indicators need review before further disbursement.'
                : p.risk === 'Medium' ? 'Some indicators are worth monitoring against upcoming milestones.'
                : p.risk === 'Low' ? 'No major anomaly is visible in the available indicators.'
                : 'Risk level is not available for this project.'}
            </span></div>
            <div className="flex gap-2"><IndianRupee size={15} className="text-muted shrink-0 mt-0.5" /><span className="text-ink">Check financial utilization alongside the risk category breakdown, not in isolation.</span></div>
          </div>
          <div className="mt-5"><Disclaimer compact /></div>
        </div>
      </div>
    </PageContainer>
  )
}