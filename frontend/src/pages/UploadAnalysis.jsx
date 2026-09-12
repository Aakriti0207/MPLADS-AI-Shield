import React, { useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FileText, Loader2, UploadCloud, X } from 'lucide-react'
import RiskBadge from '../components/risk/RiskBadge'
import { formatRiskLevel } from '../lib/formatters'
import { analyzeUpload } from '../features/upload/api'
import PageContainer from '../components/layout/PageContainer'

const MAX_FILE_BYTES = 10 * 1024 * 1024

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
  const rows = projects.map(project => headers.map(header => quote(Array.isArray(project[header === 'why_risky' ? 'why_risky' : header]) ? project[header === 'why_risky' ? 'why_risky' : header].join(' | ') : project[header])).join(','))
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
      setAnalysis(await analyzeUpload(file))
    } catch (err) {
      setError(err.message || 'Unable to analyze the uploaded dataset.')
    } finally {
      setBusy(false)
    }
  }

  const projects = analysis?.projects || []
  const filtered = useMemo(() => projects.filter(project => riskFilter === 'All' || formatRiskLevel(project.risk_level) === riskFilter), [projects, riskFilter])

  return <PageContainer maxWidth="1400px">
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-6">
      <div><div className="eyebrow">Phase 12</div><h1 className="text-3xl font-extrabold mt-1">Upload & Analyze</h1><p className="text-slate-500 mt-1">Run the existing MPLADS intelligence pipeline on a dataset without changing reference data.</p></div>
      {analysis && <button className="btn-secondary" onClick={() => downloadCsv(projects)}><Download size={16}/> Download Results CSV</button>}
    </div>

    <section className="card p-5 mb-6">
      <div
        className={`border-2 border-dashed rounded-2xl p-8 text-center transition ${dragging ? 'border-navy bg-blue-50' : 'border-slate-300 bg-slate-50'}`}
        onDragOver={event => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={event => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0]) }}
      >
        <UploadCloud className="mx-auto text-navy" size={30}/>
        <h2 className="font-bold mt-3">Drop a CSV dataset here</h2>
        <p className="text-sm text-slate-500 mt-1">or choose a file from your computer, up to 10 MB</p>
        <button className="btn-primary mt-4" onClick={() => inputRef.current?.click()}><FileText size={16}/> Browse CSV</button>
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={event => chooseFile(event.target.files?.[0])}/>
      </div>
      {file && <div className="mt-4 flex items-center justify-between gap-3 rounded-xl bg-blue-50 px-4 py-3 text-sm"><div className="flex items-center gap-3 min-w-0"><FileText className="text-navy shrink-0" size={18}/><div className="truncate"><b>{file.name}</b><div className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</div></div></div><button className="text-slate-500 hover:text-rose-700" title="Remove file" onClick={() => { setFile(null); setAnalysis(null); setError(null) }}><X size={18}/></button></div>}
      {error && <div className="mt-4 flex gap-2 items-start rounded-xl bg-rose-50 text-rose-800 px-4 py-3 text-sm"><AlertTriangle size={17} className="shrink-0 mt-0.5"/>{error}</div>}
      <div className="flex justify-end mt-4"><button className="btn-primary" disabled={!file || !!validateFile(file) || busy} onClick={analyze}>{busy ? <><Loader2 className="animate-spin" size={16}/> Analyzing Dataset...</> : <><CheckCircle2 size={16}/> Analyze Dataset</>}</button></div>
    </section>

    {busy && <div className="card p-6 mb-6 text-sm text-slate-600"><div className="flex items-center gap-2 font-semibold"><Loader2 className="animate-spin text-navy" size={18}/> Running the existing pipeline</div><div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 mt-4 text-xs"><span>✓ File validated</span><span>✓ Features generated</span><span>⟳ Compliance and anomalies</span><span>○ Risk Fusion and explanations</span></div></div>}

    {analysis && <>
      <section className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">{[['Total Projects', analysis.summary.total_projects], ['Critical', analysis.summary.critical], ['High', analysis.summary.high], ['Medium', analysis.summary.medium], ['Low', analysis.summary.low]].map(([label, value]) => <div className="card p-4" key={label}><div className="text-xs text-slate-500">{label}</div><div className="text-2xl font-extrabold mt-1">{value}</div></div>)}</section>
      <section className="card overflow-hidden"><div className="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">Analyzed projects</h2><p className="text-xs text-slate-500 mt-1">Risk scores and explanations come from Risk Fusion.</p></div><select value={riskFilter} onChange={event => setRiskFilter(event.target.value)} className="border border-slate-200 rounded-xl px-3 py-2 text-sm"><option>All</option><option>Critical</option><option>High</option><option>Medium</option><option>Low</option></select></div><div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs text-slate-500 uppercase"><tr><th className="px-4 py-3">Work ID</th><th className="px-4 py-3">State</th><th className="px-4 py-3">Score</th><th className="px-4 py-3">Level</th><th className="px-4 py-3">Why risky</th></tr></thead><tbody>{filtered.map(project => <tr key={project.work_id} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer" onClick={() => setSelected(project)}><td className="px-4 py-3 font-semibold whitespace-nowrap">{project.work_id}</td><td className="px-4 py-3">{project.state || '—'}</td><td className="px-4 py-3 font-bold">{Number(project.risk_score).toFixed(1)}</td><td className="px-4 py-3"><RiskBadge risk={formatRiskLevel(project.risk_level)}/></td><td className="px-4 py-3 max-w-[460px] truncate">{project.why_risky?.[0] || 'No current evidence; review status is based on available data.'}</td></tr>)}</tbody></table></div>{filtered.length === 0 && <div className="p-10 text-center text-slate-500">No projects match this filter.</div>}</section>
      {selected && <section className="card p-5 mt-5"><div className="flex items-start justify-between gap-4"><div><div className="eyebrow">Project detail</div><h2 className="font-bold text-lg mt-1">{selected.work_id}</h2></div><button title="Close detail" onClick={() => setSelected(null)}><X size={18}/></button></div><div className="flex items-center gap-3 mt-4"><RiskBadge risk={formatRiskLevel(selected.risk_level)}/><span className="font-bold">Risk score {Number(selected.risk_score).toFixed(1)}</span></div><h3 className="font-semibold mt-5">Why this project requires review</h3>{selected.why_risky?.length ? <ul className="list-disc pl-5 mt-2 space-y-2 text-sm text-slate-700">{selected.why_risky.map(reason => <li key={reason}>{reason}</li>)}</ul> : <p className="text-sm text-slate-500 mt-2">No anomaly or compliance evidence was generated for the available fields.</p>}<div className="flex flex-wrap gap-2 mt-4">{selected.evidence?.map(item => <span key={item} className="rounded-full bg-blue-50 text-navy px-3 py-1 text-xs font-semibold">{item}</span>)}</div></section>}
    </>}
  </PageContainer>
}