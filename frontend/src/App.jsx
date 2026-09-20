import React, { Suspense } from 'react'
import { Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import Projects from './pages/Projects'
import ProjectDetails from './pages/ProjectDetails'
import { publicRoutes, appRoutes } from './app/routes'
import { useAuth } from './context/AuthContext'
import { publicProjectPath, projectsLink } from './lib/publicTheme'

// /projects and /projects/:id are the INTERNAL, risk-aware views. Anonymous
// visitors are sent to the citizen-facing public portal equivalents
// (/public/projects, /public/projects/:id) so old links keep working and
// no public visitor lands on a page built for officials. While the session
// is still being checked we render the internal page, which shows its own
// "Checking your session" state.
function InternalOrPublic({ children, publicTarget }) {
  const { status, isAuthenticated } = useAuth()
  const params = useParams()
  const location = useLocation()
  if (status !== 'checking' && !isAuthenticated) {
    return <Navigate to={publicTarget(params, location)} replace />
  }
  return children
}

function PageFallback() {
  return (
    <div className="public-portal min-h-screen flex items-center justify-center" role="status">
      <span className="text-[15px] text-muted">Loading…</span>
    </div>
  )
}

// Centralized routing: the actual list of routes/pages lives in
// app/routes.jsx (shared with Sidebar/Topbar/Breadcrumbs). This file only
// wires that config into the public vs. protected+shell route trees.
//
// /projects and /projects/:id are deliberate exceptions: the artifact
// puts Project Explorer in the PUBLIC navigation and the Overview page's
// "Recently Monitored Projects" links straight into a project detail
// page, so both have to be reachable without a session -- unlike every
// other appRoutes entry, neither can sit behind ProtectedRoute (that
// would bounce an anonymous visitor to /login just for clicking a
// public project). Projects.jsx and ProjectDetails.jsx are each
// auth-aware and render the right chrome (public navbar vs.
// authenticated sidebar/topbar) and call the right endpoint (public vs.
// protected) based on real auth state. Both stay listed in
// app/routes.jsx (appRoutes) unchanged so Sidebar nav / Topbar title /
// Breadcrumbs keep working off that shared config -- they're just
// excluded from the loop below so they aren't rendered twice.
export default function App() {
  return <Suspense fallback={<PageFallback />}><Routes>
    {publicRoutes.map(({ path, element: Element }) => (
      <Route key={path} path={path} element={<Element />} />
    ))}
    <Route path="/projects" element={
      <InternalOrPublic publicTarget={(_p, loc) => projectsLink({ q: new URLSearchParams(loc.search).get('search') || '' })}>
        <Projects />
      </InternalOrPublic>
    } />
    <Route path="/projects/:id" element={
      <InternalOrPublic publicTarget={p => publicProjectPath(p.id)}>
        <ProjectDetails />
      </InternalOrPublic>
    } />
    <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
      {appRoutes.filter(r => r.path !== '/projects' && r.path !== '/projects/:id').map(({ path, element: Element }) => (
        <Route key={path} path={path} element={<Element />} />
      ))}
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Suspense>
}