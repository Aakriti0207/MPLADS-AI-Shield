import React, { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FileText, Loader2, UploadCloud, X } from 'lucide-react'
import { RiskBadge, Disclaimer } from '../components/UI'
import { formatRiskLevel } from '../lib/formatters'
import { analyzeUpload } from '../features/upload/api'
import { PIPELINE_STAGES } from '../lib/mockData'
import PageContainer from '../components/layout/PageContainer'

const MAX_FILE_BYTES = 10 * 1024 * 1024
const STAGE_INTERVAL_MS = 550

function validateFile(file) {
  if (!file) return 'Choose a CSV file to continue.'
  if (!file.name.toLowerCase().endsWith('.csv')) return 'Only CSV files are accepted.'
  if (file.size === 0) return 'The selected file is empty.'
  if (file.size > MAX_FILE_BYTES) return 'The selected file is larger than 10 MB.'
  return null
}

function downloadCsv(projects) {
  const headers = ['work_id', 'state', 'constituency', 'risk_score', 'risk_level', 'evidence', 'why_risky']
  const quote = value => `"${String(value ?? '').replaceAll('"', '""')}"`
  const rows = projects.map(project => headers.map(header => quote(Array.isArray(project[header]) ? project[header].join(' | ') : project[header])).join(','))
  const blob = new Blob([[headers.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'mplads-analysis-results.csv'
  link.click()
  URL.revokeObjectURL(url)
}

export default function UploadAnalysis() {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [riskFilter, setRiskFilter] = useState('All')
  const [selected, setSelected] = useState(null)
  // Cosmetic stage index only -- the real backend call below is a single
  // request/response (see features/upload/api.js), not a polling job, so
  // this timer just narrates the pipeline stages named in lib/mockData.js
  // while that one request is in flight. It always reaches the final
  // stage once the real response comes back, never before.
  const [stageIndex, setStageIndex] = useState(0)

  useEffect(() => {
    if (!busy) return
    setStageIndex(0)
    const timer = setInterval(() => {
      setStageIndex(i => Math.min(i + 1, PIPELINE_STAGES.length - 1))
    }, STAGE_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [busy])

  const chooseFile = candidate => {
    const nextError = validateFile(candidate)
    setError(nextError)
    setAnalysis(null)
    setSelected(null)
    if (!nextError) setFile(candidate)
    else setFile(null)
  }

  const analyze = async () => {
    if (!file || validateFile(file)) return
    setBusy(true)
    setError(null)
    setAnalysis(null)
    try {
      const result = await analyzeUpload(file)
      setStageIndex(PIPELINE_STAGES.length - 1)
      setAnalysis(result)
    } catch (err) {
      setError(err.message || 'Unable to analyze the uploaded dataset.')
    } finally {
      setBusy(false)
    }
  }

  const projects = analysis?.projects || []
  const filtered = useMemo(() => projects.filter(project => riskFilter === 'All' || formatRiskLevel(project.risk_level) === riskFilter), [projects, riskFilter])

  return (
    <PageContainer maxWidth="1200px">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-5">
        <div>
          <h1 className="text-[19px] font-semibold text-ink">Upload &amp; Analyze</h1>
          <p className="text-[13px] text-muted mt-0.5">Run the MPLADS AI Shield pipeline on a dataset without changing reference data.</p>
        </div>
        {analysis && <button className="btn-secondary" onClick={() => downloadCsv(projects)}><Download size={15} /> Download results CSV</button>}
      </div>

      <section className="card p-4 mb-5">
        <div
          className={`border-2 border-dashed rounded-md p-8 text-center transition ${dragging ? 'border-navy bg-info-bg' : 'border-line bg-panel'}`}
          onDragOver={event => { event.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={event => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0]) }}
        >
          <UploadCloud className="mx-auto text-navy" size={26} />
          <h2 className="font-semibold text-[13.5px] mt-2.5 text-ink">Drop a CSV dataset here</h2>
          <p className="text-xs text-muted mt-1">or choose a file from your computer, up to 10 MB</p>
          <button className="btn-primary mt-3.5" onClick={() => inputRef.current?.click()}><FileText size={14} /> Browse CSV</button>
          <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={event => chooseFile(event.target.files?.[0])} />
        </div>

        {file && (
          <div className="mt-4 flex items-center justify-between gap-3 rounded-md bg-info-bg px-4 py-3 text-sm">
            <div className="flex items-center gap-3 min-w-0">
              <FileText className="text-navy shrink-0" size={16} />
              <div className="truncate"><b className="text-ink">{file.name}</b><div className="text-xs text-muted">{(file.size / 1024).toFixed(1)} KB</div></div>
            </div>
            <button className="text-muted hover:text-ink" title="Remove file" onClick={() => { setFile(null); setAnalysis(null); setError(null) }}><X size={16} /></button>
          </div>
        )}

        {error && (
          <div className="mt-4 flex gap-2 items-start rounded-md bg-bad-bg px-4 py-3 text-sm" style={{ color: '#c0392b' }}>
            <AlertTriangle size={15} className="shrink-0 mt-0.5" />{error}
          </div>
        )}

        <div className="flex justify-end mt-4">
          <button className="btn-primary" disabled={!file || !!validateFile(file) || busy} onClick={analyze}>
            {busy ? <><Loader2 className="animate-spin" size={15} /> Analyzing dataset…</> : <><CheckCircle2 size={15} /> Analyze dataset</>}
          </button>
        </div>
      </section>

      {busy && (
        <div className="card p-4 mb-5">
          <div className="flex items-center gap-2 font-semibold text-[13px] text-ink"><Loader2 className="animate-spin text-navy" size={16} /> Running the MPLADS AI Shield pipeline</div>
          <p className="text-xs text-muted mt-1 mb-3">The backend processes this as one request -- the stage highlighted below narrates what's happening, it isn't a live per-stage status feed.</p>
          <div className="flex flex-wrap gap-2">
            {PIPELINE_STAGES.map((stage, i) => {
              const done = i < stageIndex
              const current = i === stageIndex
              return (
                <span
                  key={stage}
                  className="text-[11.5px] font-medium px-2.5 py-1.5 rounded-md border flex items-center gap-1.5"
                  style={{
                    backgroundColor: done ? '#e7f4ec' : current ? '#eef3f8' : '#f3f5f7',
                    color: done ? '#1b8a5a' : current ? '#1d63a8' : '#55636e',
                    borderColor: done ? '#bfe3d0' : current ? '#c7daee' : '#dce2e8',
                  }}
                >
                  {done ? <CheckCircle2 size={12} /> : current ? <Loader2 size={12} className="animate-spin" /> : <span className="w-2 h-2 rounded-full bg-line" />}
                  {stage}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {analysis && (
        <>
          <section className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
            {[['Total Projects', analysis.summary.total_projects], ['Critical', analysis.summary.critical], ['High', analysis.summary.high], ['Medium', analysis.summary.medium], ['Low', analysis.summary.low]].map(([label, value]) => (
              <div className="card p-3.5" key={label}><div className="text-xs text-muted">{label}</div><div className="text-[20px] font-semibold mt-1 text-ink">{value}</div></div>
            ))}
          </section>

          <section className="card overflow-hidden">
            <div className="px-4 py-3 border-b border-line flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="font-semibold text-[13.5px] text-ink">Analyzed projects</h2><p className="text-xs text-muted mt-0.5">Risk scores and explanations come from Risk Fusion.</p></div>
              <select value={riskFilter} onChange={event => setRiskFilter(event.target.value)} className="border border-line rounded-md px-3 py-1.5 text-[12.5px] bg-white">
                <option>All</option><option>Critical</option><option>High</option><option>Medium</option><option>Low</option>
              </select>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>Work ID</th><th>State</th><th>Score</th><th>Level</th><th>Why risky</th></tr></thead>
                <tbody>
                  {filtered.map(project => (
                    <tr key={project.work_id} className="hover:bg-panel cursor-pointer" onClick={() => setSelected(project)}>
                      <td className="font-semibold whitespace-nowrap text-ink font-mono">{project.work_id}</td>
                      <td>{project.state || '—'}</td>
                      <td className="font-semibold text-ink">{Number(project.risk_score).toFixed(1)}</td>
                      <td><RiskBadge risk={formatRiskLevel(project.risk_level)} /></td>
                      <td className="max-w-[420px] truncate">{project.why_risky?.[0] || 'No current evidence; review status is based on available data.'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filtered.length === 0 && <div className="p-10 text-center text-muted text-sm">No projects match this filter.</div>}
          </section>

          {selected && (
            <section className="card p-4 mt-4">
              <div className="flex items-start justify-between gap-4">
                <div><div className="eyebrow">Project detail</div><h2 className="font-semibold text-[14px] mt-1 text-ink font-mono">{selected.work_id}</h2></div>
                <button title="Close detail" onClick={() => setSelected(null)}><X size={16} /></button>
              </div>
              <div className="flex items-center gap-3 mt-3.5">
                <RiskBadge risk={formatRiskLevel(selected.risk_level)} />
                <span className="font-semibold text-[13px] text-ink">Risk score {Number(selected.risk_score).toFixed(1)}</span>
              </div>
              <h3 className="font-semibold text-[13px] mt-4 text-ink">Why this project requires review</h3>
              {selected.why_risky?.length ? (
                <div className="grid md:grid-cols-2 gap-2.5 mt-2">
                  {selected.why_risky.map(reason => (
                    <div key={reason} className="rounded-md border border-line p-3 text-[12.5px] text-ink leading-5">{reason}</div>
                  ))}
                </div>
              ) : <p className="text-sm text-muted mt-2">No anomaly or compliance evidence was generated for the available fields.</p>}
              {selected.evidence?.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {selected.evidence.map(item => <span key={item} className="rounded-full bg-info-bg text-navy px-3 py-1 text-xs font-semibold">{item}</span>)}
                </div>
              )}
              <div className="mt-4"><Disclaimer compact /></div>
            </section>
          )}
        </>
      )}
    </PageContainer>
  )
}