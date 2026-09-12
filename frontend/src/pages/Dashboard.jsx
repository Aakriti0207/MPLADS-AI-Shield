import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Banknote, CheckCircle2, FolderKanban, Gauge, ShieldAlert, TrendingUp } from 'lucide-react'
import { toNumber } from '../lib/formatters'
import LoadingState from '../components/ui/LoadingState'
import ErrorState from '../components/ui/ErrorState'
import { fetchDashboardStats } from '../features/dashboard/api'
import PageContainer from '../components/layout/PageContainer'
import DashboardKpiGrid from '../components/dashboard/DashboardKpiGrid'
import DashboardFinancialOverview from '../components/dashboard/DashboardFinancialOverview'
import DashboardRiskOverview from '../components/dashboard/DashboardRiskOverview'
import DashboardPortfolioInsights from '../components/dashboard/DashboardPortfolioInsights'
import DashboardQuickAccess from '../components/dashboard/DashboardQuickAccess'

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

 if (loading) return <PageContainer maxWidth="1500px">
  <LoadingState text="Loading dashboard…" />
 </PageContainer>

 if (error) return <PageContainer maxWidth="1500px">
  <ErrorState title="Could not load dashboard statistics" message={error} onRetry={()=>{setLoading(true); setError(null); fetchDashboardStats().then(setStats).catch(err=>setError(err.message)).finally(()=>setLoading(false))}} />
 </PageContainer>

 // --- Map the raw /dashboard/stats payload; every value defensively
 // null-checked so a legitimately-missing figure never silently becomes 0.
 const totalProjects = toNumber(stats.total_projects)
 const totalSanctioned = toNumber(stats.total_sanctioned_amount)
 const totalExpenditure = toNumber(stats.total_expenditure)
 const avgFinancialProgress = toNumber(stats.average_financial_progress)
 // average_physical_progress is genuinely unavailable in the current
 // backend data (the live endpoint returns null for it) -- surfaced as an
 // explicit "not reported" state in DashboardPortfolioInsights rather
 // than silently treated as 0%.
 const avgPhysicalProgress = toNumber(stats.average_physical_progress)
 const activeProjects = toNumber(stats.active_projects)
 const completedProjects = toNumber(stats.completed_projects)
 const delayedProjects = toNumber(stats.delayed_projects)

 const utilizationPct = (totalSanctioned && totalExpenditure!==null)
  ? Math.round((totalExpenditure/totalSanctioned)*100) : null

 const riskCounts = stats.risk_level_counts || {}
 const hasRiskCounts = Object.keys(riskCounts).length>0
 const highPlusCritical = (riskCounts.HIGH||0) + (riskCounts.CRITICAL||0)

 // Curated, not exhaustive -- prioritizes the figures a reviewer needs
 // most rather than surfacing every field the backend happens to return.
 const kpiItems = [
  { key:'total', label:'Total projects', value: totalProjects, format:'number', hint:'Full MPLADS portfolio', icon: FolderKanban, tone:'navy' },
  { key:'sanctioned', label:'Sanctioned amount', value: totalSanctioned, format:'currency', hint:'Total approved allocation', icon: Banknote, tone:'navy' },
  { key:'expenditure', label:'Expenditure', value: totalExpenditure, format:'currency', hint: utilizationPct!==null ? `${utilizationPct}% utilized` : 'Utilization not available', icon: TrendingUp, tone:'blue' },
  { key:'completed', label:'Completed projects', value: completedProjects, format:'number', hint:'Fully executed works', icon: CheckCircle2, tone:'green' },
  { key:'active', label:'Active projects', value: activeProjects, format:'number', hint:'Currently under execution', icon: Activity, tone:'blue' },
  { key:'delayed', label:'Delayed projects', value: delayedProjects, format:'number', hint:'Behind expected timeline', icon: AlertTriangle, tone:'amber' },
  { key:'avgProgress', label:'Avg. financial progress', value: avgFinancialProgress, format:'percent', hint:'Across scored projects', icon: Gauge, tone:'navy' },
  { key:'highRisk', label:'High + Critical risk', value: hasRiskCounts ? highPlusCritical : null, format:'number', hint:'Needs prioritized review', icon: ShieldAlert, tone:'red' },
 ]

 return <PageContainer maxWidth="1500px">
   <div className="mb-7">
    <div className="eyebrow">Executive monitoring</div>
    <h1 className="text-3xl font-extrabold mt-1">Dashboard overview</h1>
    <p className="text-slate-500 mt-1 max-w-2xl">A consolidated snapshot of the MPLADS project portfolio, financial execution, and AI-assisted risk signals for authorized review.</p>
   </div>

   <div className="mb-6">
    <DashboardKpiGrid items={kpiItems} />
   </div>

   <div className="grid lg:grid-cols-3 gap-5 mb-5">
    <div className="lg:col-span-2">
     <DashboardFinancialOverview
      totalSanctioned={totalSanctioned}
      totalExpenditure={totalExpenditure}
      utilizationPct={utilizationPct}
      avgFinancialProgress={avgFinancialProgress}
     />
    </div>
    <DashboardRiskOverview
     riskCounts={riskCounts}
     hasRiskCounts={hasRiskCounts}
     highPlusCritical={highPlusCritical}
    />
   </div>

   <div className="mb-5">
    <DashboardPortfolioInsights
     totalProjects={totalProjects}
     activeProjects={activeProjects}
     completedProjects={completedProjects}
     delayedProjects={delayedProjects}
     avgPhysicalProgress={avgPhysicalProgress}
     byState={stats.by_state}
     byWorkType={stats.by_work_type}
    />
   </div>

   <div className="card p-5 mb-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
     <div className="font-bold text-lg">Prioritized review</div>
     <p className="text-sm text-slate-500 mt-1 max-w-2xl">
      {hasRiskCounts
       ? <>There are <b className="text-ink">{highPlusCritical.toLocaleString()}</b> High or Critical risk projects across the portfolio. Use the Risk filter on the Projects page to review them individually with full detail and risk factors.</>
       : 'Risk-level counts are not available from the current backend data. Open Projects to review individual project risk detail.'}
     </p>
    </div>
    <Link to="/projects" className="btn-primary shrink-0">Review projects</Link>
   </div>

   <div className="mb-5">
    <DashboardQuickAccess />
   </div>

   <div className="text-xs text-slate-400 flex items-center gap-2">
    <CheckCircle2 size={14}/> AI outputs shown on this dashboard are advisory risk-prioritization signals for authorized human review. An anomaly does not, by itself, establish fraud or wrongdoing.
   </div>
 </PageContainer>
}