import React from 'react'
import Home from '../pages/Home'
import About from '../pages/About'
import Login from '../pages/Login'
import AiInsights from '../pages/AiInsights'
import Dashboard from '../pages/Dashboard'
import Projects from '../pages/Projects'
import ProjectDetails from '../pages/ProjectDetails'
import UploadAnalysis from '../pages/UploadAnalysis'
import Alerts from '../pages/Alerts'
import Analytics from '../pages/Analytics'
import AiShield from '../pages/AiShield'
import MapPage from '../pages/MapPage'
import Reports from '../pages/Reports'
import { PERMISSION } from '../lib/roles'

// Public transparency portal pages. Statistics (charts) and the map
// (Leaflet) are code-split so the landing page stays light.
const PublicProjects = React.lazy(() => import('../pages/public/PublicProjects'))
const PublicProjectDetail = React.lazy(() => import('../pages/public/PublicProjectDetail'))
const PublicMap = React.lazy(() => import('../pages/public/PublicMap'))
const PublicStatistics = React.lazy(() => import('../pages/public/PublicStatistics'))
const PublicLocations = React.lazy(() => import('../pages/public/PublicLocations'))

// Centralized route configuration.
//
// This single source of truth is consumed by:
//  - App.jsx            -> renders the actual <Routes>/<Route> tree
//  - Sidebar.jsx         -> builds nav links from entries that set `nav`
//  - Topbar.jsx/AppShell -> looks up the current page title
//  - Breadcrumbs.jsx     -> builds the breadcrumb trail (parent -> current)
//
// `publicRoutes` render outside the AppShell (no sidebar/topbar).
// `appRoutes` render inside the AppShell, behind ProtectedRoute.
// `nav` (when present) is the label shown in the sidebar; routes without
// it (e.g. the project detail page) are reachable but not top-level nav items.
// `parent` links a detail route back to its listing route for breadcrumbs.
// `permission` names the capability the route requires. ProtectedRoute
// reads the same mapping from lib/roles.js's ROUTE_PERMISSIONS, so a
// route cannot ship without a gate by accident. Sidebar builds its
// entries from NAV_BY_ROLE (also in lib/roles.js) rather than from `nav`
// below, because the LABEL is role-dependent -- an MP's "My Projects"
// and a State officer's "State Projects" are this same /projects route.
// `nav` is kept as the role-neutral name for anything still reading it.

export const publicRoutes = [
  { path: '/', element: Home, title: 'MPLADS Insight' },
  // Phase 6: public, anonymous-safe AI Insights. Aggregate-only (see
  // pages/AiInsights.jsx) -- must never redirect to /login, so it lives
  // in publicRoutes like Home/About/Login, not appRoutes+ProtectedRoute.
  { path: '/ai-insights', element: AiInsights, title: 'AI Insights' },
  { path: '/about', element: About, title: 'About' },
  // Public portal (anonymous, canonical /public/explorer/* data only).
  { path: '/public/projects', element: PublicProjects, title: 'Projects' },
  { path: '/public/projects/:id', element: PublicProjectDetail, title: 'Project details' },
  { path: '/public/map', element: PublicMap, title: 'Explore Map' },
  { path: '/public/statistics', element: PublicStatistics, title: 'Statistics' },
  { path: '/public/locations', element: PublicLocations, title: 'Explore by location' },
  { path: '/public/locations/:state', element: PublicLocations, title: 'State overview' },
  { path: '/public/locations/:state/:district', element: PublicLocations, title: 'District overview' },
  { path: '/login', element: Login, title: 'Sign in' },
]

export const appRoutes = [
  { path: '/dashboard', element: Dashboard, title: 'Overview', nav: 'Dashboard', permission: PERMISSION.VIEW_DASHBOARD },
  { path: '/projects', element: Projects, title: 'Projects', nav: 'Projects', permission: PERMISSION.VIEW_PROJECTS },
  { path: '/projects/:id', element: ProjectDetails, title: 'Project Intelligence', parent: '/projects', permission: PERMISSION.VIEW_PROJECT_DETAILS },
  { path: '/ai-shield', element: AiShield, title: 'AI Shield', nav: 'AI Shield', permission: PERMISSION.VIEW_AI_INSIGHTS },
  { path: '/upload', element: UploadAnalysis, title: 'Upload & Analyze', nav: 'Upload & Analyze', permission: PERMISSION.UPLOAD_DATA },
  { path: '/alerts', element: Alerts, title: 'Alerts', nav: 'Alerts', permission: PERMISSION.VIEW_ALERTS },
  { path: '/analytics', element: Analytics, title: 'Analytics', nav: 'Analytics', permission: PERMISSION.VIEW_ANALYTICS },
  { path: '/map', element: MapPage, title: 'Map View', nav: 'Map View', permission: PERMISSION.VIEW_MAP },
  { path: '/reports', element: Reports, title: 'Reports', nav: 'Reports', permission: PERMISSION.VIEW_REPORTS },
]

// Matches a pathname against appRoutes, supporting one ":param" segment
// (e.g. "/projects/:id"). Falls back to undefined when nothing matches.
export function matchAppRoute(pathname) {
  const exact = appRoutes.find(r => r.path === pathname)
  if (exact) return exact
  return appRoutes.find(r => {
    if (!r.path.includes(':')) return false
    const pattern = '^' + r.path.replace(/:[^/]+/g, '[^/]+') + '$'
    return new RegExp(pattern).test(pathname)
  })
}