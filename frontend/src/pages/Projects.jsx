import React,{useEffect,useMemo,useState} from 'react'
import {Link} from 'react-router-dom'
import {AlertTriangle, ChevronLeft, ChevronRight, Eye, SlidersHorizontal} from 'lucide-react'
import {formatCurrency} from '../lib/formatters'
import RiskBadge from '../components/risk/RiskBadge'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import {fetchProjects} from '../features/projects/api'
import ProjectFilters from '../components/projects/ProjectFilters'
import PageContainer from '../components/layout/PageContainer'
const PAGE_SIZE = 50

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
    fetchProjects({skip, limit: PAGE_SIZE})
   .then(data=>{
    if(cancelled) return
    setRows(data)
   })
   .catch(err=>{
    if(!cancelled) setError(err.message || 'Failed to reach the API')
   })
   .finally(()=>{ if(!cancelled) setLoading(false) })
  return ()=>{ cancelled=true }
 },[skip])

 const projects = rows

 const workTypes = useMemo(()=>[...new Set(projects.map(p=>p.workType).filter(Boolean))],[projects])

 const filtered = useMemo(()=>projects.filter(p=>
  (`${p.id} ${p.mpName} ${p.state} ${p.district} ${p.constituency}`.toLowerCase().includes(q.toLowerCase())) &&
  (risk==='All'||p.risk===risk) &&
  (workType==='All'||p.workType===workType)
 ),[projects,q,risk,workType])

 const financialPct = p => (p.sanctioned && p.expenditure!==null) ? Math.min(100, Math.round((p.expenditure/p.sanctioned)*100)) : null

 return <PageContainer maxWidth="1500px">
 <div className="mb-6">
  <div className="eyebrow">Portfolio explorer</div>
  <h1 className="text-3xl font-extrabold mt-1">Projects</h1>
  <p className="text-slate-500 mt-1">Search, filter and open a complete project intelligence view.</p>
 </div>

 <ProjectFilters query={q} onQueryChange={setQ} risk={risk} onRiskChange={setRisk} workType={workType} onWorkTypeChange={setWorkType} workTypes={workTypes}/>

 <div className="card overflow-hidden">
  <div className="p-4 border-b border-slate-200 flex items-center justify-between">
   <div className="flex items-center gap-2 text-sm font-semibold"><SlidersHorizontal size={17}/> {filtered.length} of {rows.length} loaded projects matched</div>
   <div className="text-xs text-slate-500">Live backend • showing {skip+1}–{skip+rows.length}</div>
  </div>

  {loading && <LoadingState text="Loading projects from the API…" />}

  {!loading && error && <ErrorState title="Could not load projects" message={error} onRetry={()=>setSkip(skip)} />}

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
      <div className="text-xs text-slate-500 mb-1">{formatCurrency(p.expenditure)} / {formatCurrency(p.sanctioned)}</div>
      <div className="w-full"><div className="h-2 bg-slate-100 rounded-full overflow-hidden"><div className="h-full bg-navy rounded-full" style={{width:`${pct}%`}}/></div><div className="text-xs text-slate-500 mt-1">{pct}%</div></div>
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
 </PageContainer>
}