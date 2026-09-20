import { CheckCircle2, Clock, FileCheck2, HelpCircle, FilePen } from 'lucide-react'

/**
 * Status presentation for the public portal.
 *
 * Text colours are deliberately darker than the app-wide STATUS_TONE so
 * every pill meets WCAG AA contrast (>= 4.5:1) on its tinted background,
 * and every status also carries an icon + a word, so meaning is never
 * carried by colour alone.
 *
 * The hint strings describe how the source pipeline derives each label
 * (see backend ml/status.py) -- they do not add any new claim.
 */
export const PUBLIC_STATUS = {
  Completed: {
    text: '#14683f', bg: '#e7f4ec', bar: '#1b8a5a', icon: CheckCircle2,
    hint: 'A completion record exists for this work.',
  },
  Ongoing: {
    text: '#1d4f8a', bg: '#e4eef9', bar: '#2b6cb0', icon: Clock,
    hint: 'The records show the work as partly completed or at inspection stage.',
  },
  Sanctioned: {
    text: '#0b2e4f', bg: '#eaf0f6', bar: '#5b7c99', icon: FileCheck2,
    hint: 'The work has been sanctioned; no later stage is recorded yet.',
  },
  Recommended: {
    text: '#5a4310', bg: '#fbf0de', bar: '#b7791f', icon: FilePen,
    hint: 'The work has been recommended; no sanction is recorded yet.',
  },
  'Not specified': {
    text: '#3f4b55', bg: '#eef1f3', bar: '#9aa5ae', icon: HelpCircle,
    hint: 'The records do not state a status for this work.',
  },
}

export function statusStyle(status) {
  return PUBLIC_STATUS[status] || PUBLIC_STATUS['Not specified']
}

/** Preferred display order for status lists. */
export const STATUS_ORDER = ['Completed', 'Ongoing', 'Sanctioned', 'Recommended', 'Not specified']

export function sortStatuses(rows, key = 'status') {
  const rank = value => {
    const index = STATUS_ORDER.indexOf(value)
    return index === -1 ? STATUS_ORDER.length : index
  }
  return [...rows].sort((a, b) => rank(a[key]) - rank(b[key]))
}

export const PORTAL_PATHS = {
  home: '/',
  projects: '/public/projects',
  map: '/public/map',
  statistics: '/public/statistics',
  locations: '/public/locations',
  about: '/about',
}

/** Canonical public project URL -- one identifier per project. */
export function publicProjectPath(projectId) {
  return `${PORTAL_PATHS.projects}/${encodeURIComponent(projectId)}`
}

/** Link into the project explorer with filters pre-applied. */
export function projectsLink(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  })
  const query = search.toString()
  return query ? `${PORTAL_PATHS.projects}?${query}` : PORTAL_PATHS.projects
}

export function locationPath(state, district) {
  if (!state) return PORTAL_PATHS.locations
  const base = `${PORTAL_PATHS.locations}/${encodeURIComponent(state)}`
  return district ? `${base}/${encodeURIComponent(district)}` : base
}