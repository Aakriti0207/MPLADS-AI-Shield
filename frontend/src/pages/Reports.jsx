import React,{useEffect,useMemo,useState} from 'react'
import {AlertTriangle,FileText,Loader2,Printer} from 'lucide-react'
import {money} from '../data'
import {API_BASE,apiFetch} from '../lib/api'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import {fetchDashboardStats} from '../features/dashboard/api'
import {fetchProjects} from '../features/projects/api'
import PageContainer from '../components/layout/PageContainer'

// Real backend gives risk_level as 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'.
// Same normalization used in Projects.jsx / ProjectDetails.jsx / MapPage.jsx.
const titleCase = s => s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : null

const toNumber = v => {
 if (v === null || v === undefined || v === '') return null
 const n = Number(v)
 return Number.isFinite(n) ? n : null
}

// How many of the most recently loaded projects to scan for the
// "high-priority projects" list below. The backend has no risk-level
// filter query param, so this reads one page (the API's own page cap)
// rather than the full table -- see the note under the list.
const SCAN_LIMIT = 100
const LIST_LIMIT = 8

export default function Reports(){
 const [stats,setStats]=useState(null)
 const [rows,setRows]=useState([])
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState(null)

 useEffect(()=>{
  let cancelled=false
  setLoading(true)
  setError(null)
   Promise.all([
    fetchDashboardStats(),
    fetchProjects({skip: 0, limit: SCAN_LIMIT}),
  ]).then(([statsData,projectsData])=>{
   if(cancelled) return
   setStats(statsData)
   setRows(projectsData)
  }).catch(err=>{
   if(!cancelled) setError(err.message || 'Failed to reach the API')
  }).finally(()=>{
   if(!cancelled) setLoading(false)
  })
  return ()=>{ cancelled=true }
 },[])

 // Map raw records into the fields this page renders; no name/title or
 // physical-progress field is fabricated -- the real Project schema has
 // no project name/title, and physical_progress is NULL for essentially
 // all real Phase 2 rows, so financial progress is shown instead.
 const projects = useMemo(()=>rows.map(r=>({
   id: r.id ?? '—',
   state: r.state ?? null,
   district: r.district ?? null,
   workType: r.workType ?? null,
   sanctioned: r.sanctioned,
   expenditure: r.expenditure,
   financialProgress: r.financialProgress,
   risk: r.risk,
 })),[rows])

 const highPriority = useMemo(
  ()=>projects.filter(p=>p.risk==='High'||p.risk==='Critical').slice(0,LIST_LIMIT),
  [projects]
 )

 const financialPct = p => p.financialProgress!==null
  ? Math.round(p.financialProgress)
  : ((p.sanctioned && p.expenditure!==null) ? Math.min(100, Math.round((p.expenditure/p.sanctioned)*100)) : null)

 const totalProjects = stats ? stats.total_projects ?? null : null
 const riskCounts = stats ? (stats.risk_level_counts || {}) : {}
 const highRiskCount = (riskCounts.HIGH||0) + (riskCounts.CRITICAL||0)
 const delayedCount = stats ? stats.delayed_projects ?? null : null

 const summaryItems = [
  ['Total projects', totalProjects!==null ? totalProjects.toLocaleString() : 'Not available'],
  ['High risk', stats ? highRiskCount.toLocaleString() : 'Not available'],
  ['Delayed', delayedCount!==null ? delayedCount.toLocaleString() : 'Not available'],
 ]

 const print=()=>window.print()

 return <PageContainer maxWidth="1100px">
  <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6">
   <div>
    <div className="eyebrow">Management reporting</div>
    <h1 className="text-3xl font-extrabold mt-1">Reports</h1>
    <p className="text-slate-500 mt-1">A presentation-ready summary for review meetings.</p>
   </div>
   <button onClick={print} className="btn-primary" disabled={loading || !!error}><Printer size={16}/> Print / Save PDF</button>
  </div>

  <div className="card p-7 print:shadow-none">
   <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-5">
    <div>
     <div className="eyebrow">MPLADS Insight</div>
     <h2 className="text-2xl font-extrabold mt-1">Project Monitoring Summary</h2>
     <p className="text-sm text-slate-500 mt-1">Live backend data, generated {new Date().toLocaleDateString('en-IN',{day:'2-digit',month:'long',year:'numeric'})}</p>
    </div>
    <FileText className="text-navy"/>
   </div>

   {loading && <div className="py-14 flex flex-col items-center gap-2 text-slate-500"><Loader2 className="animate-spin" size={22}/><span className="text-sm">Loading report data from the API…</span></div>}

   {!loading && error && <div className="py-10 text-center">
    <AlertTriangle className="mx-auto text-rose-600 mb-2" size={22}/>
    <div className="font-semibold text-rose-700">Could not load report data</div>
    <p className="text-sm text-slate-500 mt-1">{error}</p>
    <p className="text-xs text-slate-400 mt-1">Check that the FastAPI backend is running at {API_BASE}.</p>
   </div>}

   {!loading && !error && <>
    <div className="grid sm:grid-cols-3 gap-4 my-6">{summaryItems.map(x=><div className="rounded-xl bg-slate-50 p-4" key={x[0]}><div className="text-xs text-slate-500">{x[0]}</div><div className="text-2xl font-extrabold mt-1">{x[1]}</div></div>)}</div>

    <h3 className="font-bold">High-priority projects</h3>
    {highPriority.length===0
     ? <p className="text-sm text-slate-500 mt-3">No high or critical risk projects found in the currently loaded page of results.</p>
     : <div className="mt-3 divide-y">{highPriority.map(p=>{
        const pct = financialPct(p)
        return <div className="py-4 flex justify-between gap-4" key={p.id}>
         <div><b>{p.workType || 'Untitled work'}</b><div className="text-xs text-slate-500 mt-1">{p.id} • {p.state || '—'} • {p.district || '—'}</div></div>
         <div className="text-right text-sm"><b>{pct!==null ? `${pct}%` : 'Not available'}</b><div className="text-xs text-slate-500">financial progress</div></div>
        </div>
       })}</div>}
   <p className="text-xs text-slate-400 mt-3">Based on the first {rows.length} projects returned by the backend (maximum page size {SCAN_LIMIT}); this is not a complete portfolio ranking.</p>

    <div className="mt-7 rounded-xl bg-blue-50 p-4 text-sm text-blue-900"><b>Recommended review:</b> Validate delayed projects, compare physical and financial progress, and record authorized follow-up actions in the official workflow.</div>
   </>}

   <div className="mt-7 text-xs text-slate-400">This is a SIH prototype backed by live project data. It is not an official Government of India report.</div>
  </div>
 </PageContainer>
}