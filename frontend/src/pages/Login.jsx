import React, {useState} from 'react'
import {Link, useNavigate} from 'react-router-dom'
import {ArrowLeft, LockKeyhole, ShieldCheck} from 'lucide-react'
export default function Login(){
 const [role,setRole]=useState('District Authority'), nav=useNavigate()
 return <div className="min-h-screen grid lg:grid-cols-2 bg-white">
   <div className="hidden lg:flex bg-[#082f57] text-white p-12 flex-col justify-between">
    <Link to="/" className="flex items-center gap-3">
    <div className="h-10 w-10 rounded-xl bg-white/10 flex items-center justify-center">
    <ShieldCheck/>
    </div>
    <b>MPLADS Insight</b>
    </Link><div><div className="eyebrow !text-blue-200">Secure workspace</div>
    <h1 className="text-4xl font-extrabold mt-3">Role-based access for project monitoring teams.</h1>
    <p className="text-blue-100 mt-5 max-w-md leading-7">The prototype separates public visibility from authenticated operational workflows. MPLADS Project Intelligence Platform
    Monitor projects. Identify risks. Improve transparency.
    AI-powered monitoring for smarter public infrastructure..</p>
    </div>
    <div className="text-xs text-blue-200">Prototype login • No real credentials are collected</div>
    </div>
   <div className="flex items-center justify-center p-6">
    <div className="w-full max-w-md">
      <Link to="/" className="text-sm text-slate-500 inline-flex items-center gap-2 mb-8"><ArrowLeft size={15}/> Back to home</Link>
      <div className="card p-7"><div className="h-12 w-12 rounded-xl bg-blue-50 text-navy flex items-center justify-center"><LockKeyhole/>
      </div><h2 className="text-2xl font-extrabold mt-5">Sign in</h2>
      <p className="text-sm text-slate-500 mt-1">Access the monitoring workspace</p>
      <label className="block text-sm font-semibold mt-6">Role</label><select value={role} onChange={e=>setRole(e.target.value)} className="mt-2 w-full border border-slate-200 rounded-xl px-3 py-3">
        <option>District Authority</option>
        <option>State Nodal Officer</option>
        <option>MP Office</option><option>Administrator</option><option>Public Viewer</option>
        </select>
        <label className="block text-sm font-semibold mt-4">Email</label>
        <input className="mt-2 w-full border border-slate-200 rounded-xl px-3 py-3" placeholder="demo@example.gov.in"/>
        <label className="block text-sm font-semibold mt-4">Password</label>
        <input type="password" className="mt-2 w-full border border-slate-200 rounded-xl px-3 py-3" placeholder="••••••••"/>
        <button onClick={()=>nav('/dashboard')} className="btn-primary w-full mt-6">Continue as {role}</button>
        <div className="mt-4 text-xs text-slate-500 bg-slate-50 rounded-xl p-3">Demo mode: any values are accepted.
           Real authentication should be implemented server-side.</div>
           </div>
           </div>
        </div>
 </div>
}