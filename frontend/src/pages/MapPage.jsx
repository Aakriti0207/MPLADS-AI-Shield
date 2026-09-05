import React from 'react'
import {MapContainer,TileLayer,Marker,Popup,useMap} from 'react-leaflet'
import L from 'leaflet'
import {Link} from 'react-router-dom'
import {projects} from '../data'
import {RiskBadge,StatusBadge} from '../components/UI'
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({iconRetinaUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',iconUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'})
function Fit(){const map=useMap(); React.useEffect(()=>{map.fitBounds(projects.map(p=>[p.lat,p.lng]),{padding:[30,30]})},[map]); return null}
export default function MapPage(){
 const [risk,setRisk]=React.useState('All'), filtered=projects.filter(p=>risk==='All'||p.risk===risk)
 return <div className="p-4 md:p-8 max-w-[1500px] mx-auto"><div className="mb-5 flex flex-col md:flex-row md:items-end justify-between gap-4"><div><div className="eyebrow">Geospatial intelligence</div><h1 className="text-3xl font-extrabold mt-1">Project Map</h1><p className="text-slate-500 mt-1">Explore project distribution and risk signals across India.</p></div><div className="flex gap-2">{['All','High','Medium','Low'].map(x=><button key={x} onClick={()=>setRisk(x)} className={`btn ${risk===x?'bg-navy text-white':'btn-secondary'}`}>{x}</button>)}</div></div>
 <div className="card overflow-hidden"><div className="h-[650px]"><MapContainer center={[22.5,79]} zoom={5} scrollWheelZoom className="h-full w-full"><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><Fit/>{filtered.map(p=><Marker key={p.id} position={[p.lat,p.lng]}><Popup><div className="min-w-[220px]"><div className="font-bold">{p.name}</div><div className="text-xs text-slate-500 mt-1">{p.id} • {p.district}, {p.state}</div><div className="flex gap-2 mt-3"><StatusBadge status={p.status}/><RiskBadge risk={p.risk}/></div><Link className="text-sm font-bold text-navy inline-block mt-3" to={`/projects/${p.id}`}>Open project →</Link></div></Popup></Marker>)}</MapContainer></div></div>
 <div className="mt-3 text-xs text-slate-400">Map uses OpenStreetMap tiles. Marker coordinates are demo data and should be replaced by verified project coordinates/API data.</div>
 </div>
}