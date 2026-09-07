import React,{useEffect,useMemo,useState} from 'react'
import {Link} from 'react-router-dom'
import {AlertTriangle, ChevronLeft, ChevronRight, Eye, Loader2, Search, SlidersHorizontal} from 'lucide-react'
import {money} from '../data'
import {RiskBadge,Progress} from '../components/UI'

import { API_BASE, apiFetch } from '../lib/api'
const PAGE_SIZE = 50

// Real backend gives risk_level as 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'.
// RiskBadge / the risk filter expect Title case, so normalize once here.
const titleCase = s => s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : null

const toNumber = v => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export default function Projects(){
 const [q,setQ]=useState('')
 const [risk,setRisk]=useState('All')
 const [workType,setWorkType]=useState('All')
 const [skip,setSkip]=useState(0)
 const [rows,setRows]=useState([])
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState(null)

 useEffect(()=>{
  let cancelled=false
  setLoading(true)
  setError(null)
  apiFetch(`/projects?skip=${skip}&limit=${PAGE_SIZE}`)
   .then(res=>{
    if(!res.ok) throw new Error(`Backend returned ${res.status} ${res.statusText}`)
    return res.json()
   })
   .then(data=>{
    if(cancelled) return
    // Accept either a raw array or a {items:[...]}/{projects:[...]} wrapper.
    const list = Array.isArray(data) ? data : (data.items || data.projects || data.results || [])
    setRows(list)
   })
   .catch(err=>{
    if(!cancelled) setError(err.message || 'Failed to reach the API')
   })
   .finally(()=>{ if(!cancelled) setLoading(false) })
  return ()=>{ cancelled=true }
 },[skip])

 // Map the raw API records into the fields this page renders, once per fetch.
 const projects = useMemo(()=>rows.map(r=>({
  id: r.project_id ?? '—',
  state: r.state ?? null,
  district: r.district ?? null,
  constituency: r.constituency ?? null,
  mpName: r.mp_name ?? null,
  workType: r.work_type ?? null,
  agency: r.implementing_agency ?? null,
  sanctioned: toNumber(r.sanctioned_amount),
  expenditure: toNumber(r.expenditure),
  riskScore: toNumber(r.risk_score),
  risk: titleCase(r.risk_level),
 })),[rows])

 const workTypes = useMemo(()=>[...new Set(projects.map(p=>p.workType).filter(Boolean))],[projects])

 const filtered = useMemo(()=>projects.filter(p=>
  (`${p.id} ${p.mpName} ${p.state} ${p.district} ${p.constituency}`.toLowerCase().includes(q.toLowerCase())) &&
  (risk==='All'||p.risk===risk) &&
  (workType==='All'||p.workType===workType)
 ),[projects,q,risk,workType])

 const financialPct = p => (p.sanctioned && p.expenditure!==null) ? Math.min(100, Math.round((p.expenditure/p.sanctioned)*100)) : null

 return <div className="p-4 md:p-8 max-w-[1500px] mx-auto">
 <div className="mb-6">
  <div className="eyebrow">Portfolio explorer</div>
  <h1 className="text-3xl font-extrabold mt-1">Projects</h1>
  <p className="text-slate-500 mt-1">Search, filter and open a complete project intelligence view.</p>
 </div>

 <div className="card p-4 mb-5"><div className="grid md:grid-cols-4 gap-3">
  <div className="md:col-span-2 relative">
   <Search className="absolute left-3 top-3 text-slate-400" size={18}/>
   <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search project ID, MP, state, district..." className="w-full border border-slate-200 rounded-xl py-2.5 pl-10 pr-3"/>
  </div>
  <select value={risk} onChange={e=>setRisk(e.target.value)} className="border border-slate-200 rounded-xl px-3">
   <option>All</option><option>Critical</option><option>High</option><option>Medium</option><option>Low</option>
  </select>
  <select value={workType} onChange={e=>setWorkType(e.target.value)} className="border border-slate-200 rounded-xl px-3">
   <option>All</option>{workTypes.map(w=><option key={w}>{w}</option>)}
  </select>
 </div></div>

 <div className="card overflow-hidden">
  <div className="p-4 border-b border-slate-200 flex items-center justify-between">
   <div className="flex items-center gap-2 text-sm font-semibold"><SlidersHorizontal size={17}/> {filtered.length} of {rows.length} loaded projects matched</div>
   <div className="text-xs text-slate-500">Live backend • showing {skip+1}–{skip+rows.length}</div>
  </div>

  {loading && <div className="p-14 flex flex-col items-center gap-2 text-slate-500"><Loader2 className="animate-spin" size={22}/><span className="text-sm">Loading projects from the API…</span></div>}

  {!loading && error && <div className="p-10 text-center">
   <AlertTriangle className="mx-auto text-rose-600 mb-2" size={22}/>
   <div className="font-semibold text-rose-700">Could not load projects</div>
   <p className="text-sm text-slate-500 mt-1">{error}</p>
   <p className="text-xs text-slate-400 mt-1">Check that the FastAPI backend is running at {API_BASE}.</p>
  </div>}

  {!loading && !error && <div className="overflow-x-auto"><table className="w-full text-sm">
   <thead className="bg-slate-50 text-left text-xs text-slate-500 uppercase"><tr>
    {['Project','Location','MP / Agency','Financial','Risk',''].map(h=><th key={h} className="px-4 py-3">{h}</th>)}
   </tr></thead>
   <tbody>{filtered.map(p=>{
    const pct = financialPct(p)
    return <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50">
     <td className="px-4 py-4 min-w-[220px]"><div className="font-bold">{p.workType || 'Untitled work'}</div><div className="text-xs text-slate-500 mt-1">{p.id}</div></td>
     <td className="px-4 py-4 min-w-[150px]">{p.district || '—'}<div className="text-xs text-slate-500">{p.state || '—'}</div></td>
     <td className="px-4 py-4 min-w-[170px]">{p.mpName || '—'}<div className="text-xs text-slate-500">{p.agency || '—'}</div></td>
     <td className="px-4 py-4 min-w-[150px]">
      {pct===null ? <span className="text-xs text-slate-400">Not available</span> : <>
       <div className="text-xs text-slate-500 mb-1">{money(p.expenditure)} / {money(p.sanctioned)}</div>
       <Progress value={pct}/>
      </>}
     </td>
     <td className="px-4 py-4">
      <RiskBadge risk={p.risk}/>
      <div className="text-xs text-slate-400 mt-1">{p.riskScore!==null ? p.riskScore.toFixed(1) : '—'}</div>
     </td>
     {/* Real project_id values contain "/" (e.g. WS/MP001/2023-2024/103702),
         so it must be encoded here or the router will read it as extra path
         segments instead of one :id param. */}
     <td className="px-4 py-4"><Link to={`/projects/${encodeURIComponent(p.id)}`} className="h-9 w-9 rounded-lg border border-slate-200 inline-flex items-center justify-center text-navy"><Eye size={16}/></Link></td>
    </tr>
   })}</tbody>
  </table>
  {filtered.length===0 && <div className="p-10 text-center text-slate-500">No projects match these filters on the current page.</div>}
  </div>}

  <div className="p-4 border-t border-slate-200 flex items-center justify-between">
   <button disabled={skip===0||loading} onClick={()=>setSkip(s=>Math.max(0,s-PAGE_SIZE))} className="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"><ChevronLeft size={16}/> Previous</button>
   <div className="text-xs text-slate-500">Page {Math.floor(skip/PAGE_SIZE)+1}</div>
   <button disabled={loading||rows.length<PAGE_SIZE} onClick={()=>setSkip(s=>s+PAGE_SIZE)} className="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed">Next <ChevronRight size={16}/></button>
  </div>
 </div>
 </div>
}