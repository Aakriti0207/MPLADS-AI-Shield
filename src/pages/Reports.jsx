import React from 'react'
import {Download,FileText,Printer} from 'lucide-react'
import {projects,money} from '../data'
export default function Reports(){
 const high=projects.filter(p=>p.risk==='High'), delayed=projects.filter(p=>p.status==='Delayed')
 const print=()=>window.print()
 return <div className="p-4 md:p-8 max-w-[1100px] mx-auto"><div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6"><div><div className="eyebrow">Management reporting</div><h1 className="text-3xl font-extrabold mt-1">Reports</h1><p className="text-slate-500 mt-1">A presentation-ready summary for review meetings.</p></div><button onClick={print} className="btn-primary"><Printer size={16}/> Print / Save PDF</button></div>
 <div className="card p-7 print:shadow-none"><div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-5"><div><div className="eyebrow">MPLADS Insight</div><h2 className="text-2xl font-extrabold mt-1">Project Monitoring Summary</h2><p className="text-sm text-slate-500 mt-1">Demo reporting period: September 2026</p></div><FileText className="text-navy"/></div>
 <div className="grid sm:grid-cols-3 gap-4 my-6">{[['Total projects',projects.length],['High risk',high.length],['Delayed',delayed.length]].map(x=><div className="rounded-xl bg-slate-50 p-4" key={x[0]}><div className="text-xs text-slate-500">{x[0]}</div><div className="text-2xl font-extrabold mt-1">{x[1]}</div></div>)}</div>
 <h3 className="font-bold">High-priority projects</h3><div className="mt-3 divide-y">{high.map(p=><div className="py-4 flex justify-between gap-4"><div><b>{p.name}</b><div className="text-xs text-slate-500 mt-1">{p.id} • {p.state} • {p.category}</div></div><div className="text-right text-sm"><b>{p.physical}%</b><div className="text-xs text-slate-500">physical</div></div></div>)}</div>
 <div className="mt-7 rounded-xl bg-blue-50 p-4 text-sm text-blue-900"><b>Recommended review:</b> Validate delayed projects, compare physical and financial progress, and record authorized follow-up actions in the official workflow.</div>
 <div className="mt-7 text-xs text-slate-400">This is a SIH prototype using synthetic/demo data. It is not an official Government of India report.</div></div>
 </div>
}