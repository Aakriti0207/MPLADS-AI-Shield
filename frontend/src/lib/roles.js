/**
 * Role, permission and scope model for the frontend.
 *
 * The important property of this file: it does NOT decide anything.
 *
 * The backend resolves the authenticated user's canonical role, their
 * jurisdiction and their permission list, and returns all three from
 * GET /auth/me (see app/rbac.py + app/routes/auth.py). This module
 * reads those values and turns them into navigation, labels and gates.
 * It never infers a role from a string when the backend has already
 * told us, and it never grants a capability the backend did not list.
 *
 * Frontend gating is a usability layer -- it stops officers walking
 * into pages that will only refuse them. It is not security. Every
 * protected endpoint re-checks authorization server-side regardless of
 * what this file renders.
 */

// Canonical role keys. These are the exact values the backend's
// `role_key` field uses -- they must not drift.
export const ROLE = {
  MINISTRY: 'MINISTRY',
  STATE_NODAL: 'STATE_NODAL',
  DISTRICT_AUTHORITY: 'DISTRICT_AUTHORITY',
  MP: 'MP',
  UNSCOPED: 'UNSCOPED',
}

export const ROLE_VIEW_LABEL = {
  [ROLE.MINISTRY]: 'Ministry / Admin',
  [ROLE.STATE_NODAL]: 'State Nodal Authority',
  [ROLE.DISTRICT_AUTHORITY]: 'District Authority',
  [ROLE.MP]: 'Member of Parliament',
  [ROLE.UNSCOPED]: 'Unassigned',
}

// Permission names, mirroring app/rbac.py. Used as constants so a typo
// is a build-time-visible mistake rather than a silently-false check.
export const PERMISSION = {
  VIEW_DASHBOARD: 'VIEW_DASHBOARD',
  VIEW_PROJECTS: 'VIEW_PROJECTS',
  VIEW_PROJECT_DETAILS: 'VIEW_PROJECT_DETAILS',
  VIEW_RISK: 'VIEW_RISK',
  VIEW_ALERTS: 'VIEW_ALERTS',
  VIEW_ANALYTICS: 'VIEW_ANALYTICS',
  VIEW_REPORTS: 'VIEW_REPORTS',
  VIEW_MAP: 'VIEW_MAP',
  VIEW_FINANCIALS: 'VIEW_FINANCIALS',
  VIEW_PAYMENTS: 'VIEW_PAYMENTS',
  VIEW_COMPLIANCE: 'VIEW_COMPLIANCE',
  VIEW_DUPLICATES: 'VIEW_DUPLICATES',
  VIEW_AI_INSIGHTS: 'VIEW_AI_INSIGHTS',
  VIEW_DISTRICT_COMPARISON: 'VIEW_DISTRICT_COMPARISON',
  VIEW_REVIEW_QUEUE: 'VIEW_REVIEW_QUEUE',
  EXPORT_REPORTS: 'EXPORT_REPORTS',
  UPLOAD_DATA: 'UPLOAD_DATA',
  MANAGE_USERS: 'MANAGE_USERS',
}

const COMMON_VIEW = [
  PERMISSION.VIEW_DASHBOARD,
  PERMISSION.VIEW_PROJECTS,
  PERMISSION.VIEW_PROJECT_DETAILS,
  PERMISSION.VIEW_RISK,
  PERMISSION.VIEW_ALERTS,
  PERMISSION.VIEW_ANALYTICS,
  PERMISSION.VIEW_MAP,
  PERMISSION.VIEW_FINANCIALS,
  PERMISSION.VIEW_AI_INSIGHTS,
  PERMISSION.VIEW_REPORTS,
  PERMISSION.EXPORT_REPORTS,
]

/**
 * Fallback permission sets, mirroring app/rbac.py's ROLE_PERMISSIONS.
 *
 * These are used ONLY when the backend did not send a `permissions`
 * list at all -- an older backend, or a session restored before the
 * field existed. They are not a second source of truth: whenever the
 * API sends permissions, those win outright.
 *
 * Why fall back rather than deny everything: the backend is the real
 * authorization boundary and re-checks every request regardless, so a
 * missing field here costs nothing in security but would otherwise lock
 * a legitimate officer out of the entire application during a rollout
 * where the frontend ships ahead of the backend.
 */
export const ROLE_PERMISSIONS = {
  [ROLE.MINISTRY]: [
    ...COMMON_VIEW,
    PERMISSION.VIEW_PAYMENTS,
    PERMISSION.VIEW_COMPLIANCE,
    PERMISSION.VIEW_DUPLICATES,
    PERMISSION.VIEW_DISTRICT_COMPARISON,
    PERMISSION.VIEW_REVIEW_QUEUE,
    PERMISSION.UPLOAD_DATA,
    PERMISSION.MANAGE_USERS,
  ],
  [ROLE.STATE_NODAL]: [
    ...COMMON_VIEW,
    PERMISSION.VIEW_PAYMENTS,
    PERMISSION.VIEW_COMPLIANCE,
    PERMISSION.VIEW_DUPLICATES,
    PERMISSION.VIEW_DISTRICT_COMPARISON,
    PERMISSION.VIEW_REVIEW_QUEUE,
  ],
  [ROLE.DISTRICT_AUTHORITY]: [
    ...COMMON_VIEW,
    PERMISSION.VIEW_PAYMENTS,
    PERMISSION.VIEW_COMPLIANCE,
    PERMISSION.VIEW_DUPLICATES,
    PERMISSION.VIEW_REVIEW_QUEUE,
  ],
  [ROLE.MP]: [...COMMON_VIEW],
  [ROLE.UNSCOPED]: [],
}

export function fallbackPermissions(role) {
  return ROLE_PERMISSIONS[role] || ROLE_PERMISSIONS[ROLE.UNSCOPED]
}

/**
 * Resolve a role key from the user object returned by /auth/me.
 *
 * `role_key` is authoritative and is what the backend will enforce.
 * The free-text pattern match below is a fallback for two cases only:
 * a demo session (which has no backend account), and an older backend
 * that predates role_key. Both fall back to UNSCOPED -- never to
 * MINISTRY, because defaulting an unknown role to the widest scope is
 * precisely the escalation this rewrite removes.
 */
export function normalizeRole(userOrRole) {
  if (userOrRole && typeof userOrRole === 'object') {
    if (userOrRole.role_key) return userOrRole.role_key
    return roleFromTitle(userOrRole.role)
  }
  return roleFromTitle(userOrRole)
}

// Order matters -- admin/ministry is tested first so a title like
// "Ministry (State Cell)" is not demoted to state scope. Mirrors the
// backend's _ROLE_PATTERNS exactly.
const ROLE_PATTERNS = [
  [/admin|ministry|national/i, ROLE.MINISTRY],
  [/state\s*nodal|state/i, ROLE.STATE_NODAL],
  [/district/i, ROLE.DISTRICT_AUTHORITY],
  [/member\s+of\s+parliament|parliamentarian|\bmp\b/i, ROLE.MP],
]

export function roleFromTitle(rawRole) {
  const text = String(rawRole || '').trim()
  if (!text) return ROLE.UNSCOPED
  const match = ROLE_PATTERNS.find(([pattern]) => pattern.test(text))
  return match ? match[1] : ROLE.UNSCOPED
}

/**
 * Which dashboard component a role gets. Mirrors the backend's
 * `dashboard` field, which the API also returns directly.
 */
export const ROLE_DASHBOARD = {
  [ROLE.MINISTRY]: 'ministry',
  [ROLE.STATE_NODAL]: 'state',
  [ROLE.DISTRICT_AUTHORITY]: 'district',
  [ROLE.MP]: 'mp',
  [ROLE.UNSCOPED]: 'unscoped',
}

/**
 * Role-aware navigation.
 *
 * Each entry names an EXISTING route -- no role gets a duplicate page
 * built just for it. What changes per role is the label (an MP's
 * "My Projects" and a State officer's "State Projects" are the same
 * scoped Project Explorer) and which entries appear at all.
 *
 * `permission` is the gate. An entry is shown only when the backend
 * listed that permission for this account, so navigation and API
 * authorization cannot disagree.
 */
export const NAV_BY_ROLE = {
  [ROLE.MINISTRY]: [
    { path: '/dashboard', label: 'Dashboard', permission: PERMISSION.VIEW_DASHBOARD },
    { path: '/projects', label: 'Projects', permission: PERMISSION.VIEW_PROJECTS },
    { path: '/ai-shield', label: 'AI Shield', permission: PERMISSION.VIEW_AI_INSIGHTS },
    { path: '/upload', label: 'Upload & Analyze', permission: PERMISSION.UPLOAD_DATA },
    { path: '/alerts', label: 'Alerts', permission: PERMISSION.VIEW_ALERTS },
    { path: '/analytics', label: 'Analytics', permission: PERMISSION.VIEW_ANALYTICS },
    { path: '/map', label: 'Map View', permission: PERMISSION.VIEW_MAP },
    { path: '/reports', label: 'Reports', permission: PERMISSION.VIEW_REPORTS },
  ],
  [ROLE.STATE_NODAL]: [
    { path: '/dashboard', label: 'Overview', permission: PERMISSION.VIEW_DASHBOARD },
    { path: '/projects', label: 'State Projects', permission: PERMISSION.VIEW_PROJECTS },
    // Same dashboard route, anchored to its district-comparison block.
    { path: '/dashboard#districts', label: 'District Monitoring', permission: PERMISSION.VIEW_DISTRICT_COMPARISON },
    { path: '/ai-shield', label: 'AI Shield', permission: PERMISSION.VIEW_AI_INSIGHTS },
    { path: '/alerts', label: 'Alerts', permission: PERMISSION.VIEW_ALERTS },
    { path: '/analytics', label: 'Analytics', permission: PERMISSION.VIEW_ANALYTICS },
    { path: '/map', label: 'Map View', permission: PERMISSION.VIEW_MAP },
    { path: '/reports', label: 'Reports', permission: PERMISSION.VIEW_REPORTS },
  ],
  [ROLE.DISTRICT_AUTHORITY]: [
    { path: '/dashboard', label: 'Overview', permission: PERMISSION.VIEW_DASHBOARD },
    { path: '/projects', label: 'District Projects', permission: PERMISSION.VIEW_PROJECTS },
    { path: '/ai-shield', label: 'AI Shield', permission: PERMISSION.VIEW_AI_INSIGHTS },
    { path: '/alerts', label: 'Priority Alerts', permission: PERMISSION.VIEW_ALERTS },
    { path: '/dashboard#review-queue', label: 'Review Queue', permission: PERMISSION.VIEW_REVIEW_QUEUE },
    { path: '/map', label: 'Map View', permission: PERMISSION.VIEW_MAP },
    { path: '/reports', label: 'Reports', permission: PERMISSION.VIEW_REPORTS },
  ],
  [ROLE.MP]: [
    { path: '/dashboard', label: 'Overview', permission: PERMISSION.VIEW_DASHBOARD },
    { path: '/projects', label: 'My Projects', permission: PERMISSION.VIEW_PROJECTS },
    { path: '/ai-shield', label: 'AI Shield', permission: PERMISSION.VIEW_AI_INSIGHTS },
    { path: '/alerts', label: 'Alerts', permission: PERMISSION.VIEW_ALERTS },
    { path: '/analytics', label: 'Analytics', permission: PERMISSION.VIEW_ANALYTICS },
    { path: '/map', label: 'Map View', permission: PERMISSION.VIEW_MAP },
    { path: '/reports', label: 'Reports', permission: PERMISSION.VIEW_REPORTS },
  ],
  [ROLE.UNSCOPED]: [
    { path: '/dashboard', label: 'Overview', permission: null },
  ],
}

/** Which permission each protected route requires. */
export const ROUTE_PERMISSIONS = {
  '/dashboard': PERMISSION.VIEW_DASHBOARD,
  '/projects': PERMISSION.VIEW_PROJECTS,
  '/ai-shield': PERMISSION.VIEW_AI_INSIGHTS,
  '/upload': PERMISSION.UPLOAD_DATA,
  '/alerts': PERMISSION.VIEW_ALERTS,
  '/analytics': PERMISSION.VIEW_ANALYTICS,
  '/map': PERMISSION.VIEW_MAP,
  '/reports': PERMISSION.VIEW_REPORTS,
}

/**
 * Per-role page titles. The underlying page is shared -- only the
 * heading changes, so an MP's AI Shield and a District Authority's AI
 * Shield are the same component reading the same risk engine.
 */
export const PAGE_TITLE_BY_ROLE = {
  '/ai-shield': {
    [ROLE.MINISTRY]: 'AI Shield — National Monitoring',
    [ROLE.STATE_NODAL]: 'AI Shield — State Monitoring',
    [ROLE.DISTRICT_AUTHORITY]: 'AI Shield — District Monitoring',
    [ROLE.MP]: 'AI Shield — My Constituency',
  },
  '/projects': {
    [ROLE.MINISTRY]: 'Project Explorer',
    [ROLE.STATE_NODAL]: 'State Projects',
    [ROLE.DISTRICT_AUTHORITY]: 'District Projects',
    [ROLE.MP]: 'My Projects',
  },
  '/alerts': {
    [ROLE.MINISTRY]: 'Alerts',
    [ROLE.STATE_NODAL]: 'State Alerts',
    [ROLE.DISTRICT_AUTHORITY]: 'Priority Alerts',
    [ROLE.MP]: 'Constituency Alerts',
  },
  '/dashboard': {
    [ROLE.MINISTRY]: 'National Overview',
    [ROLE.STATE_NODAL]: 'State Monitoring Overview',
    [ROLE.DISTRICT_AUTHORITY]: 'District Operations Overview',
    [ROLE.MP]: 'Constituency Overview',
  },
}

export function pageTitleFor(path, role, fallback) {
  return PAGE_TITLE_BY_ROLE[path]?.[role] || fallback
}

/**
 * Human sentence naming the jurisdiction a view is showing.
 *
 * Prefers the backend's own `indicator`, so the label always describes
 * what the API actually filtered on rather than what the client thinks
 * it selected. This matters for trust: the scope line is a claim about
 * the data, and only the backend can make that claim truthfully.
 */
export function scopeIndicator(scope, role) {
  if (scope?.indicator) return scope.indicator
  if (!scope || scope.type === 'none') {
    return 'No jurisdiction has been assigned to this account'
  }
  if (scope.type === 'national') return 'Showing nationwide data'
  if (scope.type === 'state') return `Showing data for ${scope.name}`
  if (scope.type === 'district') return `Showing data for ${scope.name}`
  if (scope.type === 'constituency') return `Showing projects for ${scope.name}`
  return ROLE_VIEW_LABEL[role] || ''
}

/** "Constituency: ABC" / "State: Maharashtra" -- the role header line. */
export function scopeDescriptor(scope) {
  if (!scope) return null
  if (scope.type === 'state' && scope.state) return `State: ${scope.state}`
  if (scope.type === 'district' && scope.district) return `District: ${scope.district}`
  if (scope.type === 'constituency') {
    const name = scope.constituency || scope.mp_name
    return name ? `Constituency: ${name}` : null
  }
  if (scope.type === 'national') return 'Nationwide'
  return null
}

/** Role-aware empty state, so "0 projects" is never shown bare. */
export function emptyStateMessage(scope, role, fallback) {
  if (fallback) return fallback
  switch (scope?.type) {
    case 'constituency':
      return 'No projects are currently available for your constituency.'
    case 'district':
      return 'No projects are currently available for your assigned district.'
    case 'state':
      return 'No projects are currently available for your assigned state.'
    case 'national':
      return 'No projects are currently available.'
    default:
      return 'This account has no assigned jurisdiction, so no project records are available to it yet.'
  }
}