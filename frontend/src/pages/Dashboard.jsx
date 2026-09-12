import React,{useEffect,useState} from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Banknote, CheckCircle2, FolderKanban, Gauge, MapPinned } from 'lucide-react'
import { formatCurrency, formatNumber, formatPercent, toNumber } from '../lib/formatters'
import { Stat, Section, Progress, EmptyState } from '../components/UI'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import { fetchDashboardStats } from '../features/dashboard/api'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'


const RISK_ORDER = ['LOW','MEDIUM','HIGH','CRITICAL']
const riskLabel = k => k.charAt(0) + k.slice(1).toLowerCase()

export default function Dashboard(){
 const [stats,setStats]=useState(null)
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState(null)

 useEffect(()=>{
  let cancelled=false
  setLoading(true)
  setError(null)
    fetchDashboardStats()
     .then(data=>{ if(!cancelled) setStats(data) })
   .catch(err=>{ if(!cancelled) setError(err.message || 'Failed to reach the API') })
   .finally(()=>{ if(!cancelled) setLoading(false) })
  return ()=>{ cancelled=true }
 },[])

 if (loading) return <div className="p-4 md:p-8 max-w-[1500px] mx-auto">
  <LoadingState text="Loading dashboard…" />
 </div>

 if (error) return <div className="p-4 md:p-8 max-w-[1500px] mx-auto">
  <ErrorState title="Could not load dashboard statistics" message={error} onRetry={()=>{setLoading(true); setError(null); fetchDashboardStats().then(setStats).catch(err=>setError(err.message)).finally(()=>setLoading(false))}} />
 </div>

 // --- Map the raw /dashboard/stats payload; every value defensively
 // null-checked so a legitimately-missing figure never silently becomes 0.
 const totalProjects = stats.total_projects ?? null
 const totalSanctioned = toNumber(stats.total_sanctioned_amount)
 const totalExpenditure = toNumber(stats.total_expenditure)
 const avgFinancialProgress = toNumber(stats.average_financial_progress)
 // average_physical_progress is genuinely unavailable in the Phase 2 source
 // data (the live endpoint returns null for it) -- intentionally not read
 // or displayed anywhere below, per the data-honesty requirement.

 const utilizationPct = (totalSanctioned && totalExpenditure!==null)
  ? Math.round((totalExpenditure/totalSanctioned)*100) : null

 const riskCounts = stats.risk_level_counts || {}
 const riskData = RISK_ORDER.map(k=>({name:riskLabel(k), value: riskCounts[k] ?? 0}))
 const hasRiskCounts = Object.keys(riskCounts).length>0
 const highPlusCritical = (riskCounts.HIGH||0) + (riskCounts.CRITICAL||0)

 const financeChartData = (totalSanctioned!==null && totalExpenditure!==null) ? [
  {name:'Sanctioned', value: Math.round(totalSanctioned/10000000)},
  {name:'Expenditure', value: Math.round(totalExpenditure/10000000)},
 ] : []

 return <div className="p-4 md:p-8 max-w-[1500px] mx-auto">
   <div className="mb-7"><div className="eyebrow">Executive monitoring</div><h1 className="text-3xl font-extrabold mt-1">Good evening, monitoring team.</h1><p className="text-slate-500 mt-1">Live snapshot of the full MPLADS project portfolio and risk signal.</p></div>

   <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
    <Stat label="Total projects" value={formatNumber(totalProjects)} delta="Full Phase 2 portfolio" icon={FolderKanban}/>
    <Stat label="Sanctioned amount" value={formatCurrency(totalSanctioned)} delta={totalExpenditure!==null ? `${formatCurrency(totalExpenditure)} spent` : 'Not available'} icon={Banknote}/>
    <Stat label="Utilization" value={formatPercent(utilizationPct)} delta={totalExpenditure!==null ? `${formatCurrency(totalExpenditure)} spent` : 'Not available'} icon={Gauge}/>
    <Stat label="High + Critical risk" value={hasRiskCounts ? formatNumber(highPlusCritical) : 'Not available'} delta="Needs review" icon={AlertTriangle}/>
   </div>

   <div className="grid lg:grid-cols-3 gap-5">
    <div className="card p-5 lg:col-span-2">
     <Section title="Financial overview" subtitle="Sanctioned vs. spent, across the full portfolio (₹ Cr)"/>
     <div className="h-64">
      {financeChartData.length>0
       ? <ResponsiveContainer width="100%" height="100%"><BarChart data={financeChartData}><CartesianGrid vertical={false} strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="value" radius={[7,7,0,0]}>{financeChartData.map((_,i)=><Cell key={i}/>)}</Bar></BarChart></ResponsiveContainer>
       : <EmptyState text="Financial totals not available."/>}
     </div>
     {avgFinancialProgress!==null && <div className="mt-4">
      <div className="text-xs text-slate-500 mb-1">Average financial progress (scored projects)</div>
      <Progress value={Math.round(avgFinancialProgress)}/>
     </div>}
    </div>

    <div className="card p-5">
     <Section title="Risk overview" subtitle="AI-assisted advisory signal"/>
     <div className="h-52">
      {hasRiskCounts
       ? <ResponsiveContainer><PieChart><Pie data={riskData} dataKey="value" innerRadius={55} outerRadius={80} paddingAngle={3}>{riskData.map((_,i)=><Cell key={i}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer>
       : <EmptyState text="Risk breakdown not available."/>}
     </div>
     <div className="grid grid-cols-4 text-center text-xs">
      <div><b>{riskCounts.LOW ?? 0}</b><div className="text-emerald-600">Low</div></div>
      <div><b>{riskCounts.MEDIUM ?? 0}</b><div className="text-amber-600">Medium</div></div>
      <div><b>{riskCounts.HIGH ?? 0}</b><div className="text-rose-600">High</div></div>
      <div><b>{riskCounts.CRITICAL ?? 0}</b><div className="text-red-700">Critical</div></div>
     </div>
    </div>
   </div>

   <div className="grid lg:grid-cols-5 gap-5 mt-5">
    <div className="card p-5 lg:col-span-3">
     <Section title="Prioritized review" subtitle="Browse and filter individual high-risk projects" action={<Link to="/projects" className="text-sm font-semibold text-navy">Open Projects</Link>}/>
     <p className="text-sm text-slate-500">
      There are <b>{hasRiskCounts ? highPlusCritical.toLocaleString() : 'an unknown number of'}</b> High or Critical risk projects across the portfolio.
      Use the Risk filter on the Projects page to review them individually with full detail and risk factors.
     </p>
     <Link to="/projects" className="btn-secondary mt-4">Go to Projects</Link>
    </div>
    <div className="card p-5 lg:col-span-2">
     <Section title="Recent alerts" subtitle="Latest intelligence events" action={<Link to="/alerts" className="text-sm font-semibold text-navy">All alerts</Link>}/>
     <EmptyState text="Live alert integration is not connected yet for this phase."/>
    </div>
   </div>

   <div className="card mt-5 p-5"><div className="flex items-center gap-2 font-bold"><MapPinned size={18} className="text-navy"/> Geographic monitoring</div><p className="text-sm text-slate-500 mt-1">Open the map to inspect project distribution, risk concentration and individual project details.</p><Link to="/map" className="btn-secondary mt-4">Open Map View</Link></div>
   <div className="text-xs text-slate-400 mt-5 flex items-center gap-2"><CheckCircle2 size={14}/> AI outputs shown here are advisory risk-prioritization signals for authorized human review. An anomaly does not mean fraud.</div>
 </div>
}