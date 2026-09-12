import React,{useEffect,useState} from 'react'
import {AlertTriangle,BarChart3,FolderKanban,Wallet} from 'lucide-react'
import {BarChart,Bar,CartesianGrid,Cell,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts'
import {Section,Stat} from '../components/UI'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import { fetchAnalytics } from '../features/analytics/api'
import { toNumber } from '../lib/formatters'
import PageContainer from '../components/layout/PageContainer'
const TOP_N = 9

// Sort desc by value, keep the top N, fold the remainder into a single
// "Other" bucket (summed) rather than letting the chart run off-screen
// with dozens of thin bars when there are many states/work types.
function topNWithOther(rows, valueKey, labelKey, n){
 const sorted = [...rows].sort((a,b)=>b[valueKey]-a[valueKey])
 if (sorted.length<=n) return sorted
 const top = sorted.slice(0,n)
 const restSum = sorted.slice(n).reduce((a,r)=>a+r[valueKey],0)
 return [...top, {[labelKey]:'Other', [valueKey]:restSum}]
}

export default function Analytics(){
 const [stats,setStats]=useState(null)
 const [loading,setLoading]=useState(true)
 const [error,setError]=useState(null)

 useEffect(()=>{
  let cancelled=false
  setLoading(true)
  setError(null)
  fetchAnalytics()
   .then(data=>{ if(!cancelled) setStats(data) })
   .catch(err=>{ if(!cancelled) setError(err.message || 'Failed to reach the API') })
   .finally(()=>{ if(!cancelled) setLoading(false) })
  return ()=>{ cancelled=true }
 },[])

 if (loading) return <PageContainer maxWidth="1400px">
  <LoadingState text="Loading analytics…" />
 </PageContainer>

 if (error) return <PageContainer maxWidth="1400px">
  <ErrorState title="Could not load analytics" message={error} onRetry={()=>{setLoading(true); setError(null); fetchAnalytics().then(setStats).catch(err=>setError(err.message)).finally(()=>setLoading(false))}} />
 </PageContainer>

 const totalProjects = stats.total_projects ?? null
 const avgFinancialProgress = toNumber(stats.average_financial_progress)
 const riskCounts = stats.risk_level_counts || {}
 const highPlusCritical = (riskCounts.HIGH||0) + (riskCounts.CRITICAL||0)
 const hasRiskCounts = Object.keys(riskCounts).length>0

 const stateRows = (stats.by_state||[])
  .map(r=>({
   state: r.state,
   utilized: (()=>{ const n=toNumber(r.total_expenditure); return n!==null ? Number((n/10000000).toFixed(2)) : 0 })()
  }))
 const stateChartData = topNWithOther(stateRows,'utilized','state',TOP_N)
  .map(r=>({...r, state: r.state.length>12 ? r.state.slice(0,11)+'…' : r.state}))

 const workTypeRows = (stats.by_work_type||[]).map(r=>({work_type:r.work_type, count: r.count ?? 0}))
 const workTypeChartData = topNWithOther(workTypeRows,'count','work_type',TOP_N)
  .map(r=>({...r, work_type: r.work_type.length>16 ? r.work_type.slice(0,15)+'…' : r.work_type}))

 return <PageContainer maxWidth="1400px">
  <div className="mb-6"><div className="eyebrow">Portfolio intelligence</div><h1 className="text-3xl font-extrabold mt-1">Analytics</h1><p className="text-slate-500 mt-1">Real aggregate figures across the full Phase 2 project portfolio.</p></div>

  <div className="grid md:grid-cols-3 gap-4 mb-6">
   <Stat label="Average financial progress" value={avgFinancialProgress!==null ? `${Math.round(avgFinancialProgress)}%` : 'Not available'} icon={Wallet}/>
   <Stat label="High + Critical risk projects" value={hasRiskCounts ? highPlusCritical.toLocaleString() : 'Not available'} icon={AlertTriangle}/>
   <Stat label="Total projects" value={totalProjects!==null ? totalProjects.toLocaleString() : 'Not available'} icon={FolderKanban}/>
  </div>

  <div className="grid lg:grid-cols-2 gap-5">
   <div className="card p-5">
    <Section title="Expenditure by state" subtitle="₹ Crore, top states by expenditure"/>
    <div className="h-80">
     {stateChartData.length>0
      ? <ResponsiveContainer><BarChart data={stateChartData} layout="vertical"><CartesianGrid horizontal={false} strokeDasharray="3 3"/><XAxis type="number"/><YAxis dataKey="state" type="category" width={90}/><Tooltip/><Bar dataKey="utilized" radius={[0,7,7,0]}>{stateChartData.map((_,i)=><Cell key={i}/>)}</Bar></BarChart></ResponsiveContainer>
      : <div className="h-full flex items-center justify-center text-sm text-slate-400">State breakdown not available.</div>}
    </div>
   </div>
   <div className="card p-5">
    <Section title="Work-type breakdown" subtitle="Project count by work type"/>
    <div className="h-80">
     {workTypeChartData.length>0
      ? <ResponsiveContainer><BarChart data={workTypeChartData} layout="vertical"><CartesianGrid horizontal={false} strokeDasharray="3 3"/><XAxis type="number" allowDecimals={false}/><YAxis dataKey="work_type" type="category" width={110}/><Tooltip/><Bar dataKey="count" radius={[0,7,7,0]}>{workTypeChartData.map((_,i)=><Cell key={i}/>)}</Bar></BarChart></ResponsiveContainer>
      : <div className="h-full flex items-center justify-center text-sm text-slate-400">Work-type breakdown not available.</div>}
    </div>
   </div>
  </div>

  <div className="card mt-5 p-5"><Section title="How to use this view" subtitle="Reading the portfolio intelligence view"/><div className="grid md:grid-cols-3 gap-4 text-sm"><div className="rounded-xl bg-slate-50 p-4"><b>1. Detect</b><p className="text-slate-500 mt-1">Find states or work types with concentrated spend or volume.</p></div><div className="rounded-xl bg-slate-50 p-4"><b>2. Prioritize</b><p className="text-slate-500 mt-1">Open high-risk projects and inspect their evidence.</p></div><div className="rounded-xl bg-slate-50 p-4"><b>3. Verify</b><p className="text-slate-500 mt-1">Authorized officials validate the signal before action.</p></div></div></div>
 </PageContainer>
}