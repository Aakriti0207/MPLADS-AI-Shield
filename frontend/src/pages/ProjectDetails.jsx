import React,{useEffect,useState} from 'react'
import {Link,useParams} from 'react-router-dom'
import {AlertTriangle, ArrowLeft, Building2, IndianRupee, Loader2, MapPin, ShieldAlert, Sparkles, Users} from 'lucide-react'
import {money} from '../data'
import {RiskBadge,Progress,Section} from '../components/UI'
import RiskBreakdown from '../components/risk/RiskBreakdown'
import WhyRisky from '../components/risk/WhyRisky'

import {fetchProject, fetchProjectRisk} from '../features/projects/api'
import PageContainer from '../components/layout/PageContainer'

const titleCase = s => s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : null

const toNumber = v => {
 if (v === null || v === undefined || v === '') return null
 const n = Number(v)
 return Number.isFinite(n) ? n : null
}

// Small labelled value used in the risk-component grid. Renders "Not available"
// for a NULL score instead of silently showing 0 — a NULL component score
// means the source data didn't have it, which is different from a real 0.
function ScoreCell({label, value}){
 return <div className="rounded-xl bg-slate-50 p-4">
  <div className="text-xs text-slate-500">{label}</div>
  <div className="text-xl font-extrabold mt-1">{value===null ? <span className="text-sm font-semibold text-slate-400">Not available</span> : value.toFixed(2)}</div>
 </div>
}

function renderMetadata(meta){
 if (meta===null || meta===undefined || meta==='') return null
 let obj = meta
 if (typeof meta === 'string'){
  try { obj = JSON.parse(meta) } catch { return <p className="text-sm text-slate-600 whitespace-pre-wrap">{meta}</p> }
 }
 if (typeof obj === 'object'){
  const entries = Object.entries(obj)
  if (entries.length===0) return null
  return <div className="grid sm:grid-cols-2 gap-3">{entries.map(([k,v])=>
   <div key={k} className="text-sm"><span className="text-slate-500">{k}: </span><span className="font-semibold">{v===null||v===undefined||v==='' ? 'Not available' : String(v)}</span></div>
  )}</div>
 }
 return <p className="text-sm text-slate-600">{String(obj)}</p>
}

export default function ProjectDetails(){
 const {id}=useParams()
 const [raw,setRaw]=useState(null)
 const [riskResult,setRiskResult]=useState(null)
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState(null)
 const [notFound,setNotFound]=useState(false)

 useEffect(()=>{
  let cancelled=false
  setLoading(true)
  setError(null)
  setNotFound(false)
  // id comes back from useParams already URL-decoded by React Router, so a
  // real project_id like "WS/MP001/2023-2024/103702" is a plain string here.
  // Re-encode it before putting it in the API path so the slashes survive
  // as part of the path segment instead of being read as extra segments.
  Promise.allSettled([fetchProject(id), fetchProjectRisk(id)])
   .then(([project, risk])=>{
    if(cancelled) return
    if(project.status === 'rejected') { setNotFound(true); return }
    setRaw(project.value.raw)
    if(risk.status === 'fulfilled') setRiskResult(risk.value)
   })
   .catch(err=>{ if(!cancelled) setError(err.message || 'Failed to reach the API') })
   .finally(()=>{ if(!cancelled) setLoading(false) })
  return ()=>{ cancelled=true }
 },[id])

 if (loading) return <PageContainer maxWidth="1400px">
  <Link to="/projects" className="inline-flex items-center gap-2 text-sm text-slate-500 mb-5"><ArrowLeft size={15}/> Back to projects</Link>
  <div className="card p-14 flex flex-col items-center gap-2 text-slate-500"><Loader2 className="animate-spin" size={22}/><span className="text-sm">Loading project…</span></div>
 </PageContainer>

 if (notFound) return <PageContainer maxWidth="1400px">
  <Link to="/projects" className="inline-flex items-center gap-2 text-sm text-slate-500 mb-5"><ArrowLeft size={15}/> Back to projects</Link>
  <div className="card p-10 text-center">
   <AlertTriangle className="mx-auto text-amber-600 mb-2" size={22}/>
   <div className="font-semibold">Project not found</div>
   <p className="text-sm text-slate-500 mt-1">No project with ID <span className="font-mono">{id}</span> exists in the backend.</p>
  </div>
 </PageContainer>

 if (error) return <PageContainer maxWidth="1400px">
  <Link to="/projects" className="inline-flex items-center gap-2 text-sm text-slate-500 mb-5"><ArrowLeft size={15}/> Back to projects</Link>
  <div className="card p-10 text-center">
   <AlertTriangle className="mx-auto text-rose-600 mb-2" size={22}/>
   <div className="font-semibold text-rose-700">Could not load this project</div>
   <p className="text-sm text-slate-500 mt-1">{error}</p>
   <p className="text-xs text-slate-400 mt-1">Check that the FastAPI backend is running at {API_BASE}.</p>
  </div>
 </PageContainer>

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
  financialRisk: toNumber(raw.financial_risk_score),
  paymentRisk: toNumber(raw.payment_risk_score),
  executionRisk: toNumber(raw.execution_risk_score),
  peerAnomaly: toNumber(raw.peer_anomaly_score),
  isolationForest: toNumber(raw.isolation_forest_score),
  anomalyRisk: toNumber(raw.anomaly_risk_score),
  duplicateRisk: toNumber(raw.duplicate_risk_score),
  maxSimilarity: toNumber(raw.raw_max_similarity),
  similarWorkId: raw.most_similar_work_id ?? null,
  reasons: riskResult?.reasons?.length ? riskResult.reasons : [raw.risk_reason_1, raw.risk_reason_2, raw.risk_reason_3].filter(Boolean),
  metadata: raw.risk_metadata ?? null,
 }

 const financialPct = (p.sanctioned && p.expenditure!==null) ? Math.min(100, Math.round((p.expenditure/p.sanctioned)*100)) : null
 const riskGaugePct = p.riskScore!==null ? Math.min(100, Math.max(0, p.riskScore)) : null

 return <PageContainer maxWidth="1400px"><Link to="/projects" className="inline-flex items-center gap-2 text-sm text-slate-500 mb-5"><ArrowLeft size={15}/> Back to projects</Link>

 <div className="card p-6"><div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
  <div>
   <div className="eyebrow">{p.id}{p.workType ? ` • ${p.workType}` : ''}</div>
   <h1 className="text-3xl font-extrabold mt-2">{p.workType || 'Untitled work'}</h1>
   <div className="flex flex-wrap gap-4 text-sm text-slate-500 mt-3">
    <span className="inline-flex gap-1 items-center"><MapPin size={15}/>{p.district || 'Not available'}, {p.state || 'Not available'}</span>
    <span className="inline-flex gap-1 items-center"><Users size={15}/>{p.constituency || 'Not available'}{p.mpName ? ` • ${p.mpName}` : ''}</span>
    <span className="inline-flex gap-1 items-center"><Building2 size={15}/>{p.agency || 'Not available'}</span>
   </div>
  </div>
  <div className="flex gap-2"><RiskBadge risk={p.risk}/></div>
 </div>

 <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-7">
  <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">Sanctioned</div><div className="text-xl font-extrabold mt-1">{p.sanctioned!==null ? money(p.sanctioned) : 'Not available'}</div></div>
  <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">Expenditure</div><div className="text-xl font-extrabold mt-1">{p.expenditure!==null ? money(p.expenditure) : 'Not available'}</div></div>
  <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">Financial progress</div><div className="mt-2">{financialPct===null ? <span className="text-sm font-semibold text-slate-400">Not available</span> : <Progress value={financialPct}/>}</div></div>
  <div className="rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">Risk score</div><div className="text-xl font-extrabold mt-1">{p.riskScore!==null ? `${p.riskScore.toFixed(1)} / 100` : 'Not available'}</div></div>
 </div></div>

 <div className="grid lg:grid-cols-3 gap-5 mt-5">
  <div className="lg:col-span-2 space-y-5">

   <div className="card p-6">
    <Section title="Risk factors" subtitle="Reasons the model flagged this project"/>
    <WhyRisky reasons={p.reasons} evidence={riskResult?.source_signal_summary?.signals || []}/>
   </div>

   <div className="card p-6">
    <Section title="Risk component breakdown" subtitle="Individual signals behind the overall risk score"/>
    <RiskBreakdown risk={raw}/>
   </div>

   <div className="card p-6">
    <Section title="Similarity check" subtitle="Closest matching work order, if any"/>
    {p.similarWorkId || p.maxSimilarity!==null ? <div className="grid sm:grid-cols-2 gap-4 text-sm">
     <div><div className="text-slate-500 text-xs">Most similar work ID</div><div className="font-semibold mt-1">{p.similarWorkId || 'Not available'}</div></div>
     <div><div className="text-slate-500 text-xs">Similarity score</div><div className="font-semibold mt-1">{p.maxSimilarity!==null ? p.maxSimilarity.toFixed(3) : 'Not available'}</div></div>
    </div> : <p className="text-sm text-slate-500">No similarity data recorded for this project.</p>}
   </div>

   {p.metadata!==null && <div className="card p-6">
    <Section title="Risk metadata" subtitle="Additional context supplied by the model"/>
    {renderMetadata(p.metadata) || <p className="text-sm text-slate-500">No additional metadata recorded.</p>}
   </div>}

  </div>

  <div className="card p-6 h-fit">
   <div className="flex items-center gap-2 font-bold"><Sparkles className="text-navy" size={19}/> AI Risk Intelligence</div>
   <p className="text-xs text-slate-500 mt-1">Advisory signal • human verification required</p>
   <div className="mt-6 flex items-end justify-between">
    <div><div className="text-4xl font-extrabold">{p.riskScore!==null ? p.riskScore.toFixed(1) : '—'}</div><div className="text-xs text-slate-500">risk score / 100</div></div>
    <RiskBadge risk={p.risk}/>
   </div>
   <div className="h-3 bg-slate-100 rounded-full mt-4"><div className="h-full bg-navy rounded-full" style={{width:`${riskGaugePct ?? 0}%`}}/></div>
   <div className="mt-6 space-y-3 text-sm">
    <div className="flex gap-2"><ShieldAlert size={17} className="text-rose-600 shrink-0"/><span>
     {p.risk==='Critical'?'Multiple strong risk signals were detected — prioritize immediate human review.'
      :p.risk==='High'?'Several risk indicators need review before further disbursement.'
      :p.risk==='Medium'?'Some indicators are worth monitoring against upcoming milestones.'
      :p.risk==='Low'?'No major anomaly is visible in the available indicators.'
      :'Risk level is not available for this project.'}
    </span></div>
    <div className="flex gap-2"><IndianRupee size={17} className="text-slate-500 shrink-0"/><span>Check financial utilization alongside the risk component breakdown, not in isolation.</span></div>
   </div>
   <div className="mt-6 rounded-xl bg-amber-50 border border-amber-100 p-3 text-xs text-amber-800">AI-generated information is advisory. Anomaly does not mean fraud. Final decisions, verification and official action remain with authorized authorities.</div>
  </div>
 </div>
 </PageContainer>
}