import React from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { BarChart3, BellRing, FileText, FolderKanban, LayoutDashboard, LogIn, Map, Menu, ShieldCheck, UploadCloud, X } from 'lucide-react'
import { navItems } from '../data'
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

const icons = {Dashboard:LayoutDashboard,Projects:FolderKanban,'Upload & Analyze':UploadCloud,Alerts:BellRing,Analytics:BarChart3,'Map View':Map,Reports:FileText}
export default function Layout(){
  const [open,setOpen]=useState(false)
  const loc=useLocation()
  const nav=useNavigate()
  const { logout } = useAuth()
  const title = loc.pathname==='/dashboard'?'Overview':loc.pathname.includes('/projects/')?'Project Intelligence':navItems.find(x=>x[1]===loc.pathname)?.[0] || 'MPLADS Insight'
  return <div className="min-h-screen">
    <aside className={`fixed z-40 inset-y-0 left-0 w-64 bg-[#082f57] text-white p-5 transform transition md:translate-x-0 ${open?'translate-x-0':'-translate-x-full'}`}>
      <div className="flex items-center justify-between mb-8">
        <NavLink to="/" className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-white/10 flex items-center justify-center"><ShieldCheck size={22}/></div>
          <div><div className="font-bold leading-tight">MPLADS Insight</div><div className="text-[10px] text-blue-200">Monitoring & Risk Intelligence</div></div>
        </NavLink>
        <button onClick={()=>setOpen(false)} className="md:hidden"><X/></button>
      </div>
      <div className="eyebrow !text-blue-200 mb-3">Workspace</div>
      <nav className="space-y-1">
        {navItems.map(([label,path])=>{const I=icons[label]; return <NavLink key={path} to={path} onClick={()=>setOpen(false)} className={({isActive})=>`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm ${isActive?'bg-white text-navy font-semibold':'text-blue-100 hover:bg-white/10'}`}><I size={18}/>{label}</NavLink>})}
      </nav>
      <div className="mt-8 rounded-2xl bg-white/10 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck size={16}/> AI Advisory Layer</div>
        <p className="text-xs text-blue-100 mt-2 leading-5">Risk signals are advisory and support—not replace—authorized government review.</p>
      </div>
      <button
        type="button"
        onClick={() => { logout(); nav('/login') }}
        className="absolute bottom-5 left-5 right-5 btn bg-white/10 hover:bg-white/20 text-white"
      ><LogIn size={16}/> Sign out</button>
    </aside>
    {open && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={()=>setOpen(false)}/>}
    <main className="md:ml-64">
      <header className="sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-slate-200">
        <div className="h-16 px-4 md:px-8 flex items-center justify-between">
          <div className="flex items-center gap-3"><button className="md:hidden" onClick={()=>setOpen(true)}><Menu/></button><div><div className="font-bold">{title}</div><div className="text-xs text-slate-500">Public-sector project monitoring workspace</div></div></div>
          <div className="flex items-center gap-2"><NavLink to="/alerts" className="h-9 w-9 rounded-xl border border-slate-200 flex items-center justify-center"><BellRing size={17}/></NavLink><NavLink to="/login" className="hidden sm:flex btn-secondary !py-2"><LogIn size={15}/> Login</NavLink></div>
        </div>
      </header>
      <Outlet/>
    </main>
  </div>
}