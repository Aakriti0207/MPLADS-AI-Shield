import React from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Banknote, CheckCircle2, FolderKanban, Gauge, MapPinned } from 'lucide-react'
import { projects, alerts, money } from '../data'
import { Stat, RiskBadge, StatusBadge, Section, Progress } from '../components/UI'
import { BarChart, Bar, CartesianGrid, Cell, PieChart, Pie, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function Dashboard(){
 const total=projects.reduce((a,p)=>a+p.sanctioned,0), util=projects.reduce((a,p)=>a+p.utilized,0)
 const status=[{name:'Completed',value:projects.filter(p=>p.status==='Completed').length},{name:'Ongoing',value:projects.filter(p=>p.status==='Ongoing').length},{name:'Delayed',value:projects.filter(p=>p.status==='Delayed').length}]
 const cat=Object.entries(projects.reduce((a,p)=>(a[p.category]=(a[p.category]||0)+1,a),{})).map(([name,value])=>({name,value})).slice(0,6)
 const high=projects.filter(p=>p.risk==='High')
 return <div className="p-4 md:p-8 max-w-[1500px] mx-auto">
   <div className="mb-7"><div className="eyebrow">Executive monitoring</div><h1 className="text-3xl font-extrabold mt-1">Good evening, monitoring team.</h1><p className="text-slate-500 mt-1">Here is the latest demo snapshot of project delivery and risk.</p></div>
   <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
    <Stat label="Total projects" value={projects.length} delta="Across 20 demo projects" icon={FolderKanban}/>
    <Stat label="Sanctioned amount" value={money(total)} delta="Aggregated demo portfolio" icon={Banknote}/>
    <Stat label="Utilization" value={`${Math.round(util/total*100)}%`} delta={`${money(util)} utilized`} icon={Gauge}/>
    <Stat label="High-risk projects" value={high.length} delta="Needs review" icon={AlertTriangle}/>
   </div>
   <div className="grid lg:grid-cols-3 gap-5">
    <div className="card p-5 lg:col-span-2"><Section title="Portfolio delivery" subtitle="Projects by current status"/><div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={status}><CartesianGrid vertical={false} strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="value" radius={[7,7,0,0]}>{status.map((_,i)=><Cell key={i}/>)}</Bar></BarChart></ResponsiveContainer></div></div>
    <div className="card p-5"><Section title="Risk overview" subtitle="AI-assisted advisory signal"/><div className="h-52"><ResponsiveContainer><PieChart><Pie data={[{name:'Low',value:projects.filter(p=>p.risk==='Low').length},{name:'Medium',value:projects.filter(p=>p.risk==='Medium').length},{name:'High',value:high.length}]} dataKey="value" innerRadius={55} outerRadius={80} paddingAngle={3}>{[0,1,2].map(i=><Cell key={i}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div><div className="grid grid-cols-3 text-center text-xs"><div><b>{projects.filter(p=>p.risk==='Low').length}</b><div className="text-emerald-600">Low</div></div><div><b>{projects.filter(p=>p.risk==='Medium').length}</b><div className="text-amber-600">Medium</div></div><div><b>{high.length}</b><div className="text-rose-600">High</div></div></div></div>
   </div>
   <div className="grid lg:grid-cols-5 gap-5 mt-5">
    <div className="card p-5 lg:col-span-3"><Section title="High-risk projects" subtitle="Prioritized for human review" action={<Link to="/projects" className="text-sm font-semibold text-navy">View all</Link>}/><div className="space-y-3">{high.slice(0,4).map(p=><Link to={`/projects/${p.id}`} key={p.id} className="block rounded-xl border border-slate-200 p-4 hover:bg-slate-50"><div className="flex justify-between gap-3"><div><div className="font-semibold">{p.name}</div><div className="text-xs text-slate-500 mt-1">{p.id} • {p.state} • {p.category}</div></div><RiskBadge risk={p.risk}/></div><div className="mt-3 grid grid-cols-2 gap-4"><div><div className="text-xs text-slate-500">Physical</div><Progress value={p.physical}/></div><div><div className="text-xs text-slate-500">Financial</div><Progress value={p.financial}/></div></div></Link>)}</div></div>
    <div className="card p-5 lg:col-span-2"><Section title="Recent alerts" subtitle="Latest intelligence events" action={<Link to="/alerts" className="text-sm font-semibold text-navy">All alerts</Link>}/><div className="space-y-3">{alerts.slice(0,5).map(a=><div key={a.id} className="border-b border-slate-100 pb-3 last:border-0"><div className="flex justify-between gap-2"><span className={`text-xs font-bold ${a.severity==='High'?'text-rose-600':a.severity==='Medium'?'text-amber-600':'text-emerald-600'}`}>{a.severity.toUpperCase()}</span><span className="text-xs text-slate-400">{a.date}</span></div><div className="font-semibold text-sm mt-1">{a.title}</div><div className="text-xs text-slate-500 mt-1">{a.project} • {a.status}</div></div>)}</div></div>
   </div>
   <div className="card mt-5 p-5"><div className="flex items-center gap-2 font-bold"><MapPinned size={18} className="text-navy"/> Geographic monitoring</div><p className="text-sm text-slate-500 mt-1">Open the map to inspect project distribution, risk concentration and individual project details.</p><Link to="/map" className="btn-secondary mt-4">Open Map View</Link></div>
   <div className="text-xs text-slate-400 mt-5 flex items-center gap-2"><CheckCircle2 size={14}/> AI outputs shown here are advisory signals for authorized review.</div>
 </div>
}