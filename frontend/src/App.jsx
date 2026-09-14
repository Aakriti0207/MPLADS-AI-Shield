import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import Projects from './pages/Projects'
import ProjectDetails from './pages/ProjectDetails'
import { publicRoutes, appRoutes } from './app/routes'

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
  return <Routes>
    {publicRoutes.map(({ path, element: Element }) => (
      <Route key={path} path={path} element={<Element />} />
    ))}
    <Route path="/projects" element={<Projects />} />
    <Route path="/projects/:id" element={<ProjectDetails />} />
    <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
      {appRoutes.filter(r => r.path !== '/projects' && r.path !== '/projects/:id').map(({ path, element: Element }) => (
        <Route key={path} path={path} element={<Element />} />
      ))}
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}