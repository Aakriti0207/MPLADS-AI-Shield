const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'
const DEMO_ROLE_KEY = 'mplads_demo_role'
const DEMO_ROLES = new Set(['ministry', 'state', 'district', 'mp'])

export function isDemoModeEnabled() {
  return DEMO_MODE
}

export function getDemoRole() {
  if (!DEMO_MODE) return null
  const role = sessionStorage.getItem(DEMO_ROLE_KEY)
  return DEMO_ROLES.has(role) ? role : null
}

export function setDemoRole(role) {
  if (!DEMO_MODE || !DEMO_ROLES.has(role)) return false
  sessionStorage.setItem(DEMO_ROLE_KEY, role)
  return true
}

export function clearDemoRole() {
  sessionStorage.removeItem(DEMO_ROLE_KEY)
}

export function isValidDemoRole(role) {
  return DEMO_MODE && DEMO_ROLES.has(role)
}
