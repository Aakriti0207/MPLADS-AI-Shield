import React,{useState} from 'react'
import {Link} from 'react-router-dom'
import {BellRing,CheckCircle2,Clock3} from 'lucide-react'
import {alerts,riskClass} from '../data'
import {Badge} from '../components/UI'
export default function Alerts(){
 const [sev,setSev]=useState('All'), filtered=alerts.filter(a=>sev==='All'||a.severity===sev)
 return <div className="p-4 md:p-8 max-w-[1200px] mx-auto"><div className="mb-6"><div className="eyebrow">Risk & exception centre</div><h1 className="text-3xl font-extrabold mt-1">Alerts</h1><p className="text-slate-500 mt-1">Prioritized advisory signals generated from project indicators.</p></div>
 <div className="flex gap-2 mb-5">{['All','High','Medium','Low'].map(x=><button key={x} onClick={()=>setSev(x)} className={`btn ${sev===x?'bg-navy text-white':'btn-secondary'}`}>{x}</button>)}</div>
 <div className="space-y-3">{filtered.map(a=><div className="card p-5" key={a.id}><div className="flex flex-col md:flex-row md:items-start justify-between gap-4"><div className="flex gap-4"><div className={`h-10 w-10 rounded-xl flex items-center justify-center ${a.severity==='High'?'bg-rose-50 text-rose-600':a.severity==='Medium'?'bg-amber-50 text-amber-600':'bg-emerald-50 text-emerald-600'}`}><BellRing size={18}/></div><div><div className="flex flex-wrap gap-2 items-center"><Badge className={a.severity==='High'?'bg-rose-50 text-rose-700':a.severity==='Medium'?'bg-amber-50 text-amber-700':'bg-emerald-50 text-emerald-700'}>{a.severity}</Badge><span className="text-xs text-slate-500">{a.type}</span></div><h3 className="font-bold mt-2">{a.title}</h3><p className="text-sm text-slate-500 mt-1">{a.detail}</p><div className="text-xs text-slate-400 mt-3">{a.id} • {a.date}</div></div></div><div className="flex items-center gap-2 text-xs text-slate-500"><Clock3 size={15}/>{a.status}</div></div><div className="mt-4 flex gap-2"><Link to={`/projects/${a.project}`} className="btn-secondary !py-2">Open project</Link><button className="btn-secondary !py-2"><CheckCircle2 size={15}/> Mark reviewed</button></div></div>)}</div>
 </div>
}