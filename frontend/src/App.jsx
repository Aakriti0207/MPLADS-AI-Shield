import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import Projects from './pages/Projects'
import { publicRoutes, appRoutes } from './app/routes'

// Centralized routing: the actual list of routes/pages lives in
// app/routes.jsx (shared with Sidebar/Topbar/Breadcrumbs). This file only
// wires that config into the public vs. protected+shell route trees.
//
// /projects is a deliberate exception (Phase 4): the artifact puts
// Project Explorer in the PUBLIC navigation, so it has to be reachable
// without a session -- unlike every other appRoutes entry, it can't sit
// behind ProtectedRoute. Projects.jsx itself is auth-aware and renders
// the right chrome (public navbar vs. authenticated sidebar/topbar) and
// calls the right endpoint (public vs. protected) based on real auth
// state. It stays listed in app/routes.jsx (appRoutes) unchanged so
// Sidebar nav / Topbar title / Breadcrumbs keep working off that shared
// config -- it's just excluded from the loop below so it isn't rendered
// twice.
export default function App() {
  return <Routes>
    {publicRoutes.map(({ path, element: Element }) => (
      <Route key={path} path={path} element={<Element />} />
    ))}
    <Route path="/projects" element={<Projects />} />
    <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
      {appRoutes.filter(r => r.path !== '/projects').map(({ path, element: Element }) => (
        <Route key={path} path={path} element={<Element />} />
      ))}
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}   