import Home from '../pages/Home'
import Login from '../pages/Login'
import Dashboard from '../pages/Dashboard'
import Projects from '../pages/Projects'
import ProjectDetails from '../pages/ProjectDetails'
import UploadAnalysis from '../pages/UploadAnalysis'
import Alerts from '../pages/Alerts'
import Analytics from '../pages/Analytics'
import AiShield from '../pages/AiShield'
import MapPage from '../pages/MapPage'
import Reports from '../pages/Reports'

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

export const publicRoutes = [
  { path: '/', element: Home, title: 'MPLADS Insight' },
  { path: '/login', element: Login, title: 'Sign in' },
]

export const appRoutes = [
  { path: '/dashboard', element: Dashboard, title: 'Overview', nav: 'Dashboard' },
  { path: '/projects', element: Projects, title: 'Projects', nav: 'Projects' },
  { path: '/projects/:id', element: ProjectDetails, title: 'Project Intelligence', parent: '/projects' },
  { path: '/ai-shield', element: AiShield, title: 'AI Shield', nav: 'AI Shield' },
  { path: '/upload', element: UploadAnalysis, title: 'Upload & Analyze', nav: 'Upload & Analyze' },
  { path: '/alerts', element: Alerts, title: 'Alerts', nav: 'Alerts' },
  { path: '/analytics', element: Analytics, title: 'Analytics', nav: 'Analytics' },
  { path: '/map', element: MapPage, title: 'Map View', nav: 'Map View' },
  { path: '/reports', element: Reports, title: 'Reports', nav: 'Reports' },
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