import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import { publicRoutes, appRoutes } from './app/routes'

// Centralized routing: the actual list of routes/pages lives in
// app/routes.jsx (shared with Sidebar/Topbar/Breadcrumbs). This file only
// wires that config into the public vs. protected+shell route trees.
export default function App() {
  return <Routes>
    {publicRoutes.map(({ path, element: Element }) => (
      <Route key={path} path={path} element={<Element />} />
    ))}
    <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
      {appRoutes.map(({ path, element: Element }) => (
        <Route key={path} path={path} element={<Element />} />
      ))}
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
