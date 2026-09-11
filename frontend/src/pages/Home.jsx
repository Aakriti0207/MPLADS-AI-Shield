import React,{useEffect,useState} from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight, BarChart3, BellRing, CheckCircle2, FileSearch, Loader2, Map, ShieldCheck, Sparkles } from 'lucide-react'
import { apiFetch } from '../lib/api'
import { useAuth } from '../context/AuthContext'

const money = n => `₹${(n/10000000).toFixed(2)} Cr`

const toNumber = v => {
 if (v === null || v === undefined || v === '') return null
 const n = Number(v)
 return Number.isFinite(n) ? n : null
}

export default function Home(){
 const { isAuthenticated, status } = useAuth()
 const [stats,setStats]=useState(null)
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState(null)

 useEffect(()=>{
  // /dashboard/stats is a protected endpoint. Home is the public landing
  // page, so anonymous visitors must never trigger a request to it (that
  // would just be a guaranteed 401) -- backend protection stays intact,
  // and only authenticated visitors see live figures here.
  if (status === 'loading') return
  if (!isAuthenticated) {
   setLoading(false)
   setError(null)
   setStats(null)
   return
  }
  let cancelled=false
  setLoading(true)
  setError(null)
  apiFetch('/dashboard/stats')
   .then(res=>{
    if(!res.ok) throw new Error(`Backend returned ${res.status} ${res.statusText}`)
    return res.json()
   })
   .then(data=>{ if(!cancelled) setStats(data) })
   .catch(err=>{ if(!cancelled) setError(err.message || 'Failed to reach the API') })
   .finally(()=>{ if(!cancelled) setLoading(false) })
  return ()=>{ cancelled=true }
 },[isAuthenticated,status])

 const totalProjects = stats ? (stats.total_projects ?? null) : null
 const totalSanctioned = stats ? toNumber(stats.total_sanctioned_amount) : null
 const totalExpenditure = stats ? toNumber(stats.total_expenditure) : null
 const riskCounts = stats ? (stats.risk_level_counts || {}) : {}
 const hasRiskCounts = stats ? Object.keys(riskCounts).length>0 : false
 const highPlusCritical = (riskCounts.HIGH||0) + (riskCounts.CRITICAL||0)
 // Guarded so a missing/zero sanctioned amount can never produce NaN/Infinity.
 const utilizationPct = (totalSanctioned && totalExpenditure!==null)
  ? Math.round((totalExpenditure/totalSanctioned)*100) : null

 const snapshotItems = [
  ['Projects', totalProjects!==null ? totalProjects.toLocaleString() : 'Not available'],
  ['High + Critical risk', hasRiskCounts ? highPlusCritical.toLocaleString() : 'Not available'],
  ['Sanctioned', totalSanctioned!==null ? money(totalSanctioned) : 'Not available'],
  ['Expenditure', totalExpenditure!==null ? money(totalExpenditure) : 'Not available'],
 ]

 return <div className="min-h-screen bg-white">
   <header className="border-b border-slate-200 bg-white"><div className="max-w-7xl mx-auto px-5 h-16 flex items-center justify-between"><Link to="/" className="flex items-center gap-3"><div className="h-10 w-10 bg-navy text-white rounded-xl flex items-center justify-center"><ShieldCheck/></div><div><b>MPLADS Insight</b><div className="text-[10px] text-slate-500">Project Monitoring & Risk Intelligence</div></div></Link><div className="flex gap-2"><Link to="/dashboard" className="btn-secondary">Public Dashboard</Link><Link to="/login" className="btn-primary">Login <ArrowRight size={15}/></Link></div></div></header>

   <section className="bg-gradient-to-br from-[#082f57] to-[#0d4c86] text-white"><div className="max-w-7xl mx-auto px-5 py-20 md:py-24 grid md:grid-cols-2 gap-12 items-center">
    <div><div className="inline-flex items-center gap-2 rounded-full bg-white/10 border border-white/20 px-3 py-1 text-xs font-semibold mb-5"><Sparkles size={14}/> AI-assisted monitoring layer</div><h1 className="text-4xl md:text-6xl font-extrabold leading-tight">From project data to <span className="text-blue-200">actionable oversight.</span></h1><p className="text-blue-100 mt-5 max-w-xl leading-7">A modern monitoring workspace for tracking MPLADS projects, financial utilization, geographic spread and emerging risk signals.</p><div className="flex flex-wrap gap-3 mt-7"><Link to="/dashboard" className="btn bg-white text-navy hover:bg-blue-50">Explore Dashboard <ArrowRight size={16}/></Link><Link to="/projects" className="btn bg-white/10 border border-white/20 text-white">Browse Projects</Link></div></div>

    <div className="card bg-white/10 border-white/20 p-5 backdrop-blur">
     <div className="text-sm text-blue-100 mb-4">Live portfolio snapshot</div>

     {(loading || status==='loading') && <div className="rounded-xl bg-white/10 p-6 flex items-center justify-center gap-2 text-blue-100"><Loader2 className="animate-spin" size={18}/><span className="text-sm">Loading live figures…</span></div>}

     {!loading && status!=='loading' && !isAuthenticated && <div className="rounded-xl bg-white/10 p-4 text-sm text-blue-100">
      <div className="font-semibold text-white">Sign in to view live figures</div>
      <p className="mt-1 text-xs">Portfolio snapshot data is only shown to authenticated users. <Link to="/login" className="underline">Login</Link> to see it here.</p>
     </div>}

     {!loading && status!=='loading' && isAuthenticated && error && <div className="rounded-xl bg-white/10 p-4 text-sm text-blue-100">
      <div className="flex items-center gap-2 font-semibold text-white"><AlertTriangle size={16}/> Could not load live figures</div>
      <p className="mt-1 text-xs">{error}</p>
     </div>}

     {!loading && status!=='loading' && isAuthenticated && !error && <>
      <div className="grid grid-cols-2 gap-3">{snapshotItems.map(x=><div key={x[0]} className="rounded-xl bg-white/10 p-4"><div className="text-xs text-blue-100">{x[0]}</div><div className="text-xl font-extrabold mt-1">{x[1]}</div></div>)}</div>
      <div className="mt-4 rounded-xl bg-white p-4 text-slate-800"><div className="flex justify-between text-sm"><span>Overall utilization</span><b>{utilizationPct!==null ? `${utilizationPct}%` : 'Not available'}</b></div><div className="h-2 bg-slate-100 rounded-full mt-2"><div className="h-full bg-navy rounded-full" style={{width:`${utilizationPct ?? 0}%`}}/></div></div>
     </>}
    </div>
   </div></section>

   <section className="max-w-7xl mx-auto px-5 py-16"><div className="text-center max-w-2xl mx-auto"><div className="eyebrow">What the platform adds</div><h2 className="text-3xl font-extrabold mt-2">More than a data portal</h2><p className="text-slate-500 mt-3">Designed as an intelligence and workflow layer over project information—not a replacement for official systems.</p></div><div className="grid md:grid-cols-3 gap-5 mt-10">{[[BarChart3,'Decision dashboard','Turn scattered project indicators into one operational view.'],[BellRing,'Early risk alerts','Surface risk signals and utilization patterns for review.'],[Map,'Geographic intelligence','Understand project concentration and risk across states and districts.'],[FileSearch,'Project 360°','See financial, risk, and agency information together.'],[CheckCircle2,'Review workflow','Keep human verification and official decision-making in the loop.'],[ShieldCheck,'Trust & governance','Clearly label AI outputs as advisory with audit-ready design principles.']].map(([I,t,d])=><div className="card p-6" key={t}><div className="h-11 w-11 rounded-xl bg-blue-50 text-navy flex items-center justify-center"><I/></div><h3 className="font-bold mt-4">{t}</h3><p className="text-sm text-slate-500 mt-2 leading-6">{d}</p></div>)}</div></section>

   <footer className="border-t border-slate-200"><div className="max-w-7xl mx-auto px-5 py-7 text-sm text-slate-500 flex flex-wrap justify-between gap-3"><span>© 2026 MPLADS Insight — SIH prototype</span><span>AI-assisted advisory signals • Not an official Government of India portal</span></div></footer>
 </div>
}