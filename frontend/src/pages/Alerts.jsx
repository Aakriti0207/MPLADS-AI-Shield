import React,{useEffect,useState} from 'react'
import {Link} from 'react-router-dom'
import {AlertTriangle,BellRing,ChevronLeft,ChevronRight,Loader2} from 'lucide-react'
import {Badge} from '../components/UI'

import { API_BASE, apiFetch } from '../lib/api'
const PAGE_SIZE = 50

const SEVERITY_STYLES = {
 critical: {icon:'bg-red-100 text-red-800', badge:'bg-red-100 text-red-800'},
 high:     {icon:'bg-rose-50 text-rose-600', badge:'bg-rose-50 text-rose-700'},
 medium:   {icon:'bg-amber-50 text-amber-600', badge:'bg-amber-50 text-amber-700'},
 low:      {icon:'bg-emerald-50 text-emerald-600', badge:'bg-emerald-50 text-emerald-700'},
}
const severityLabel = s => s ? s.charAt(0).toUpperCase()+s.slice(1) : 'Unknown'

const ALERT_TYPE_LABEL = {
 high_risk_project: 'High risk project',
 possible_duplicate: 'Possible duplicate',
 financial_risk: 'Financial risk',
 payment_risk: 'Payment risk',
 execution_risk: 'Execution risk',
 peer_anomaly: 'Peer anomaly',
 anomaly_detection: 'Anomaly detection',
 anomaly_risk: 'Anomaly risk',
}

export default function Alerts(){
 const [sev,setSev]=useState('All')
 const [skip,setSkip]=useState(0)
 const [rows,setRows]=useState([])
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState(null)

 useEffect(()=>{
  let cancelled=false
  setLoading(true)
  setError(null)
  apiFetch(`/alerts?skip=${skip}&limit=${PAGE_SIZE}`)
   .then(res=>{
    if(!res.ok) throw new Error(`Backend returned ${res.status} ${res.statusText}`)
    return res.json()
   })
   .then(data=>{ if(!cancelled) setRows(Array.isArray(data) ? data : []) })
   .catch(err=>{ if(!cancelled) setError(err.message || 'Failed to reach the API') })
   .finally(()=>{ if(!cancelled) setLoading(false) })
  return ()=>{ cancelled=true }
 },[skip])

 const filtered = rows.filter(a => sev==='All' || (a.severity||'').toLowerCase()===sev.toLowerCase())

 return <div className="p-4 md:p-8 max-w-[1200px] mx-auto">
  <div className="mb-4">
   <div className="eyebrow">Risk & exception centre</div>
   <h1 className="text-3xl font-extrabold mt-1">Alerts</h1>
   <p className="text-slate-500 mt-1">Generated live from real Phase 2 risk signals — AI-assisted advisory signal, human verification required. Anomaly does not mean fraud.</p>
  </div>

  <div className="flex gap-2 mb-5">{['All','Critical','High','Medium','Low'].map(x=>
   <button key={x} onClick={()=>setSev(x)} className={`btn ${sev===x?'bg-navy text-white':'btn-secondary'}`}>{x}</button>
  )}</div>

  {loading && <div className="card p-14 flex flex-col items-center gap-2 text-slate-500"><Loader2 className="animate-spin" size={22}/><span className="text-sm">Loading alerts…</span></div>}

  {!loading && error && <div className="card p-10 text-center">
   <AlertTriangle className="mx-auto text-rose-600 mb-2" size={22}/>
   <div className="font-semibold text-rose-700">Could not load alerts</div>
   <p className="text-sm text-slate-500 mt-1">{error}</p>
   <p className="text-xs text-slate-400 mt-1">Check that the FastAPI backend is running at {API_BASE}.</p>
  </div>}

  {!loading && !error && <>
   <div className="space-y-3">{filtered.map(a=>{
    const sevKey = (a.severity||'').toLowerCase()
    const style = SEVERITY_STYLES[sevKey] || {icon:'bg-slate-100 text-slate-600', badge:'bg-slate-100 text-slate-600'}
    return <div className="card p-5" key={a.alert_id}>
     <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
      <div className="flex gap-4">
       <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${style.icon}`}><BellRing size={18}/></div>
       <div>
        <div className="flex flex-wrap gap-2 items-center">
         <Badge className={style.badge}>{severityLabel(a.severity)}</Badge>
         <span className="text-xs text-slate-500">{ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}</span>
        </div>
        <p className="text-sm text-slate-700 mt-2">{a.message}</p>
        <div className="text-xs text-slate-400 mt-3">{a.project_id}</div>
       </div>
      </div>
     </div>
     <div className="mt-4 flex gap-2">
      <Link to={`/projects/${encodeURIComponent(a.project_id)}`} className="btn-secondary !py-2">Open project</Link>
     </div>
    </div>
   })}</div>
   {filtered.length===0 && <div className="card p-10 text-center text-slate-500">No alerts match this filter on the current page.</div>}

   <div className="flex items-center justify-between mt-5">
    <button disabled={skip===0||loading} onClick={()=>setSkip(s=>Math.max(0,s-PAGE_SIZE))} className="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed"><ChevronLeft size={16}/> Previous</button>
    <div className="text-xs text-slate-500">Page {Math.floor(skip/PAGE_SIZE)+1}</div>
    <button disabled={loading||rows.length<PAGE_SIZE} onClick={()=>setSkip(s=>s+PAGE_SIZE)} className="btn-secondary disabled:opacity-40 disabled:cursor-not-allowed">Next <ChevronRight size={16}/></button>
   </div>
  </>}
 </div>
}