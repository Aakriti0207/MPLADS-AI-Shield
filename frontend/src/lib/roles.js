// Maps the backend's real `user.role` string (confirmed live in
// /auth/me -- see e.g. context/__tests__/AuthContext.test.jsx, which
// exercises "Administrator" and "District Authority") onto the four
// artifact-defined view scopes. This is the ONLY place that mapping
// lives, so if the backend's exact role strings change, only this file
// needs updating.
//
// Unknown/missing roles fall back to 'ministry' (the broadest, national
// view) rather than hiding data -- safer default for an internal
// monitoring tool than silently showing nothing.

const ROLE_MAP = [
  [/admin/i, 'ministry'],
  [/ministry/i, 'ministry'],
  [/state/i, 'state'],
  [/district/i, 'district'],
  [/member of parliament|\bmp\b/i, 'mp'],
]

export function normalizeRole(rawRole) {
  if (!rawRole) return 'ministry'
  const match = ROLE_MAP.find(([pattern]) => pattern.test(rawRole))
  return match ? match[1] : 'ministry'
}

export const ROLE_VIEW_LABEL = {
  ministry: 'Ministry / Admin',
  state: 'State Nodal Authority',
  district: 'District Authority',
  mp: 'Member of Parliament',
}

// Which sidebar nav entries (by their `nav` label in app/routes.jsx) each
// view scope gets. Everything not listed for a role is hidden -- e.g.
// Upload & Analyze is a Ministry-only tool per the product brief.
export const NAV_BY_ROLE = {
  ministry: ['Dashboard', 'Projects', 'AI Shield', 'Upload & Analyze', 'Alerts', 'Analytics', 'Map View', 'Reports'],
  state: ['Dashboard', 'Projects', 'AI Shield', 'Alerts', 'Analytics', 'Map View', 'Reports'],
  district: ['Dashboard', 'Projects', 'AI Shield', 'Alerts', 'Map View', 'Reports'],
  mp: ['Dashboard', 'Projects', 'AI Shield', 'Alerts', 'Map View'],
}