import React, { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Download, FileSpreadsheet, FileText, Loader2, ShieldAlert } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import ErrorState from '../components/ui/ErrorState'
import LoadingState from '../components/ui/LoadingState'
import { Disclaimer } from '../components/UI'
import { fetchDashboardStats } from '../features/dashboard/api'
import { downloadReportFile, fetchReportPreview, fetchReportsMeta } from '../features/reports/api'
import { formatCurrency, formatNumber, formatPercent } from '../lib/formatters'
import { RISK_ORDER, riskTone } from '../lib/theme'
import { useAuth } from '../context/AuthContext'

const FIELD_LABEL = 'text-[11px] font-medium text-muted mb-1 block'
const SELECT_CLASS = 'w-full border border-line rounded-md px-3 py-2 text-[13px] bg-white text-ink'
const INPUT_CLASS = 'w-full border border-line rounded-md px-3 py-2 text-[13px] bg-white text-ink'

const EMPTY_FILTERS = {
  state: '', district: '', constituency: '', category: '', riskLevel: '', dateFrom: '', dateTo: '',
}

export default function Reports() {
  const { isDemo } = useAuth()

  const [metaLoading, setMetaLoading] = useState(true)
  const [metaError, setMetaError] = useState(null)
  const [meta, setMeta] = useState(null)
  const [dashboard, setDashboard] = useState(null)

  const [reportType, setReportType] = useState('')
  const [filters, setFilters] = useState(EMPTY_FILTERS)

  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState(null)
  const [report, setReport] = useState(null)
  const [reportFilters, setReportFilters] = useState(null) // filters used for the currently shown report

  const [downloadingFormat, setDownloadingFormat] = useState(null)
  const [downloadError, setDownloadError] = useState(null)

  useEffect(() => {
    if (isDemo) {
      setMetaLoading(false)
      setMeta({ role: 'Demo', scope_available: false, unavailable_reason: 'Scoped reporting is not available in demo mode. Sign in with a real account to generate reports.' })
      return undefined
    }
    let cancelled = false
    setMetaLoading(true)
    setMetaError(null)
    Promise.all([fetchReportsMeta(), fetchDashboardStats().catch(() => null)])
      .then(([metaData, dashboardData]) => {
        if (cancelled) return
        setMeta(metaData)
        setDashboard(dashboardData)
        if (metaData.report_types?.length > 0) setReportType(metaData.report_types[0].id)
      })
      .catch(err => { if (!cancelled) setMetaError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setMetaLoading(false) })
    return () => { cancelled = true }
  }, [isDemo])

  const states = useMemo(() => (dashboard?.by_state || []).map(s => s.state).filter(Boolean).sort(), [dashboard])
  const categories = useMemo(() => (dashboard?.by_work_type || []).map(c => c.work_type).filter(Boolean).sort(), [dashboard])

  function updateFilter(key, value) {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS)
  }

  async function handleGenerate() {
    if (!reportType) return
    setGenerating(true)
    setGenerateError(null)
    setDownloadError(null)
    try {
      const data = await fetchReportPreview({ reportType, ...filters })
      setReport(data)
      setReportFilters({ reportType, ...filters })
    } catch (err) {
      setReport(null)
      setReportFilters(null)
      setGenerateError(err.message || 'Report generation failed. Please try again.')
    } finally {
      setGenerating(false)
    }
  }

  async function handleDownload(format) {
    if (!reportFilters) return
    setDownloadingFormat(format)
    setDownloadError(null)
    try {
      await downloadReportFile(reportFilters, format)
    } catch (err) {
      setDownloadError(err.message || 'Download failed. Please try again.')
    } finally {
      setDownloadingFormat(null)
    }
  }

  if (metaLoading) {
    return (
      <PageContainer maxWidth="1000px">
        <ReportsHeader />
        <LoadingState text="Checking report availability…" />
      </PageContainer>
    )
  }

  if (metaError) {
    return (
      <PageContainer maxWidth="1000px">
        <ReportsHeader />
        <ErrorState title="Could not load Reports" message={metaError} />
      </PageContainer>
    )
  }

  if (!meta?.scope_available) {
    return (
      <PageContainer maxWidth="1000px">
        <ReportsHeader />
        <div className="card p-10 text-center">
          <ShieldAlert className="mx-auto mb-2 text-muted" size={20} />
          <div className="font-semibold text-[13.5px] text-ink">Scoped reporting is not available for this account.</div>
          <p className="text-sm text-muted mt-1 max-w-md mx-auto">{meta?.unavailable_reason}</p>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer maxWidth="1000px">
      <ReportsHeader />

      {/* A. Generate Report */}
      <div className="card p-5 mb-4">
        <h2 className="text-[14.5px] font-semibold text-ink">Generate Report</h2>
        <p className="text-xs text-muted mt-0.5">Scope: {meta.scope_label}</p>

        <div className="flex flex-wrap gap-2 mt-4">
          {meta.report_types.map(rt => (
            <button
              key={rt.id}
              type="button"
              onClick={() => setReportType(rt.id)}
              className={`text-left rounded-md border px-3.5 py-2.5 text-[13px] transition-colors ${reportType === rt.id ? 'border-navy bg-panel' : 'border-line bg-white hover:bg-panel'}`}
              style={{ minWidth: 220 }}
            >
              <div className={`font-semibold ${reportType === rt.id ? 'text-navy' : 'text-ink'}`}>{rt.label}</div>
              <div className="text-xs text-muted mt-0.5">{rt.description}</div>
            </button>
          ))}
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
          <div>
            <label className={FIELD_LABEL}>State</label>
            <select value={filters.state} onChange={e => updateFilter('state', e.target.value)} className={SELECT_CLASS}>
              <option value="">All</option>
              {states.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className={FIELD_LABEL}>Category</label>
            <select value={filters.category} onChange={e => updateFilter('category', e.target.value)} className={SELECT_CLASS}>
              <option value="">All</option>
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className={FIELD_LABEL}>Risk Level</label>
            <select value={filters.riskLevel} onChange={e => updateFilter('riskLevel', e.target.value)} className={SELECT_CLASS}>
              <option value="">All</option>
              {RISK_ORDER.map(l => <option key={l} value={l}>{riskTone(l).label}</option>)}
            </select>
          </div>
          <div>
            <label className={FIELD_LABEL}>District</label>
            <input value={filters.district} onChange={e => updateFilter('district', e.target.value)} placeholder="Exact district name" className={INPUT_CLASS} />
          </div>
          <div>
            <label className={FIELD_LABEL}>Constituency</label>
            <input value={filters.constituency} onChange={e => updateFilter('constituency', e.target.value)} placeholder="Exact constituency name" className={INPUT_CLASS} />
          </div>
          <div>
            <label className={FIELD_LABEL}>Sanctioned from</label>
            <input type="date" value={filters.dateFrom} onChange={e => updateFilter('dateFrom', e.target.value)} className={INPUT_CLASS} />
          </div>
          <div>
            <label className={FIELD_LABEL}>Sanctioned to</label>
            <input type="date" value={filters.dateTo} onChange={e => updateFilter('dateTo', e.target.value)} className={INPUT_CLASS} />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 mt-4">
          <button onClick={handleGenerate} disabled={generating || !reportType} className="btn-primary disabled:opacity-50">
            {generating ? <><Loader2 className="animate-spin" size={15} /> Generating report…</> : <><FileText size={15} /> Generate Report</>}
          </button>
          <button type="button" onClick={resetFilters} className="btn-secondary" disabled={generating}>Reset Filters</button>

          {report && (
            <>
              <button onClick={() => handleDownload('csv')} disabled={downloadingFormat !== null} className="btn-secondary disabled:opacity-50">
                {downloadingFormat === 'csv' ? <Loader2 className="animate-spin" size={15} /> : <FileSpreadsheet size={15} />} Download CSV
              </button>
              <button onClick={() => handleDownload('pdf')} disabled={downloadingFormat !== null} className="btn-secondary disabled:opacity-50">
                {downloadingFormat === 'pdf' ? <Loader2 className="animate-spin" size={15} /> : <Download size={15} />} Download PDF
              </button>
            </>
          )}
        </div>

        {generateError && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-bad-bg px-3 py-2.5">
            <AlertTriangle className="mt-0.5 shrink-0" size={14} style={{ color: '#c0392b' }} />
            <p className="text-xs" style={{ color: '#c0392b' }}>{generateError}</p>
          </div>
        )}
        {downloadError && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-bad-bg px-3 py-2.5">
            <AlertTriangle className="mt-0.5 shrink-0" size={14} style={{ color: '#c0392b' }} />
            <p className="text-xs" style={{ color: '#c0392b' }}>{downloadError}</p>
          </div>
        )}
      </div>

      {/* B. Available Exports */}
      <div className="card p-5 mb-4">
        <h2 className="text-[14.5px] font-semibold text-ink">Recent Reports</h2>
        <p className="text-xs text-muted mt-0.5">Report history is not currently stored by the backend.</p>
        <p className="text-sm text-muted mt-3">Generate a report using the available monitoring data above — each report is built fresh from live data.</p>
      </div>

      {/* C. Report Information */}
      {report && <ReportInformation report={report} />}
    </PageContainer>
  )
}

function ReportsHeader() {
  return (
    <div className="mb-5 no-print">
      <h1 className="text-[19px] font-semibold text-ink">Reports</h1>
      <p className="text-[13px] text-muted mt-0.5">Generate monitoring reports using verified MPLADS project and AI Shield data.</p>
    </div>
  )
}

function ReportInformation({ report }) {
  const riskEntries = Object.entries(report.risk_level_counts || {})
  const generated = new Date(report.generated_at)

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
        <div>
          <div className="eyebrow">MPLADS AI Shield</div>
          <h2 className="text-[17px] font-semibold mt-1 text-ink">{report.title}</h2>
          <p className="text-xs text-muted mt-1">
            Generated {Number.isNaN(generated.getTime()) ? 'just now' : generated.toLocaleString('en-IN')} · Scope: {report.scope}
          </p>
        </div>
        <FileText className="text-navy shrink-0" size={18} />
      </div>

      <div className="mt-3 rounded-md bg-good-bg px-3 py-2 text-xs text-ink inline-block">Report generated successfully.</div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 my-5">
        <SummaryTile label="Total projects" value={formatNumber(report.total_projects)} />
        <SummaryTile label="Sanctioned amount" value={formatCurrency(report.total_sanctioned_amount)} />
        <SummaryTile label="Expenditure" value={formatCurrency(report.total_expenditure)} />
        <SummaryTile label="Avg. financial progress" value={formatPercent(report.average_financial_progress)} />
      </div>

      <h3 className="font-semibold text-[13.5px] text-ink">AI Shield Risk Indicators</h3>
      {riskEntries.length === 0 ? (
        <p className="text-sm text-muted mt-2">AI Shield risk scoring is not available for the selected scope.</p>
      ) : (
        <div className="mt-2.5 overflow-x-auto">
          <table className="data-table">
            <thead><tr>{['Risk Level', 'Projects'].map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {riskEntries.map(([level, count]) => (
                <tr key={level}>
                  <td><span style={{ color: riskTone(level).color }} className="font-medium">{riskTone(level).label}</span></td>
                  <td>{formatNumber(count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="grid sm:grid-cols-3 gap-3 mt-3.5">
        <SummaryTile label="Projects Requiring Review" value={formatNumber(report.projects_requiring_review)} />
        <SummaryTile label="Duplicate Indicators" value={formatNumber(report.duplicate_indicators)} />
        <SummaryTile label="Anomaly Indicators" value={formatNumber(report.anomaly_indicators)} />
      </div>

      <h3 className="font-semibold text-[13.5px] text-ink mt-6">Priority Review Items</h3>
      {report.priority_projects.length === 0 ? (
        <p className="text-sm text-muted mt-2.5">No High or Critical risk projects found for the selected scope.</p>
      ) : (
        <div className="mt-2.5 divide-y divide-line">
          {report.priority_projects.map(p => (
            <div className="py-3 flex justify-between gap-4" key={p.project_id}>
              <div>
                <b className="text-ink text-[13px]">{p.work_type || 'Untitled work'}</b>
                <div className="text-xs text-muted mt-1 font-mono">{p.project_id} · {p.state || '—'} · {p.constituency || '—'}</div>
                {p.risk_reasons.length > 0 && <div className="text-xs text-muted mt-1">{p.risk_reasons[0]}</div>}
              </div>
              <div className="text-right text-sm shrink-0">
                <b style={{ color: riskTone(p.risk_level).color }}>{riskTone(p.risk_level).label}</b>
                <div className="text-xs text-muted">{p.risk_score !== null && p.risk_score !== undefined ? `score ${p.risk_score}` : 'score not available'}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {report.data_quality_notes.length > 0 && (
        <>
          <h3 className="font-semibold text-[13.5px] text-ink mt-6">Data Quality / Limitations</h3>
          <ul className="mt-2 space-y-1 list-disc list-inside text-sm text-muted">
            {report.data_quality_notes.map(note => <li key={note}>{note}</li>)}
          </ul>
        </>
      )}

      <div className="mt-6"><Disclaimer /></div>
      <div className="mt-3 text-xs text-muted">This is a SIH prototype backed by live project data. It is not an official Government of India report.</div>
    </div>
  )
}

function SummaryTile({ label, value }) {
  return (
    <div className="rounded-md bg-panel p-3.5">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-[18px] font-semibold mt-1 text-ink">{value}</div>
    </div>
  )
}