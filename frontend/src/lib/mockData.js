// ---------------------------------------------------------------------
// DEMO / PLACEHOLDER DATA
// ---------------------------------------------------------------------
// Everything in this file is illustrative, not live backend data. Each
// export below says exactly which backend capability is missing and
// what real endpoint/field would replace it. When those exist, delete
// the corresponding block here and swap the caller over to the real
// fetch -- nothing else in the app should need to change shape, since
// callers already consume these as plain arrays/objects.
// ---------------------------------------------------------------------

// Used by: components/home/IndiaStateGrid.jsx, purely for the cartogram's
// grid POSITION (row/col) of each state -- not a statistic, just layout,
// so it's safe to use regardless of auth state. Any tier color or number
// drawn on top of this layout comes from the real GET /dashboard/stats
// `by_state` array (state + total_expenditure) passed into that
// component, never from a field here.
export const STATE_STATS = [
  { name: 'Jammu & Kashmir', row: 1, col: 4 },
  { name: 'Punjab', row: 2, col: 3 },
  { name: 'Himachal Pradesh', row: 2, col: 4 },
  { name: 'Uttarakhand', row: 2, col: 5 },
  { name: 'Haryana', row: 3, col: 3 },
  { name: 'Delhi', row: 3, col: 4 },
  { name: 'Uttar Pradesh', row: 3, col: 5 },
  { name: 'Assam', row: 3, col: 8 },
  { name: 'Rajasthan', row: 4, col: 2 },
  { name: 'Madhya Pradesh', row: 4, col: 4 },
  { name: 'Bihar', row: 4, col: 6 },
  { name: 'West Bengal', row: 4, col: 7 },
  { name: 'Gujarat', row: 5, col: 1 },
  { name: 'Chhattisgarh', row: 5, col: 5 },
  { name: 'Jharkhand', row: 5, col: 6 },
  { name: 'Odisha', row: 5, col: 7 },
  { name: 'Maharashtra', row: 6, col: 3 },
  { name: 'Telangana', row: 6, col: 5 },
  { name: 'Andhra Pradesh', row: 7, col: 5 },
  { name: 'Karnataka', row: 7, col: 3 },
  { name: 'Tamil Nadu', row: 8, col: 4 },
  { name: 'Kerala', row: 8, col: 3 },
]

// Used by: UploadAnalysis.jsx, purely as stage LABELS for the visual
// pipeline while the real (single-request) backend call is in flight.
// No data here is fabricated -- it's the same processing pipeline your
// ML layer already documents, just narrated stage-by-stage on the
// frontend instead of via a real per-stage status endpoint.
// Needs: if the backend later exposes a job/stage-status endpoint (e.g.
// POST /upload-analyze returning a job_id, then GET /jobs/:id/status),
// swap the timer-driven advance() below for real polling.
export const PIPELINE_STAGES = [
  'File validation', 'Cleaning & canonicalization', 'Feature engineering',
  'Compliance engine', 'Financial anomaly detection', 'Timeline analysis',
  'Duplicate similarity', 'Payment intelligence', 'Isolation forest',
  'Risk fusion & explainability',
]

// Used by: ProjectDetails.jsx lifecycle stepper.
// Needs: real recommendation_date / sanction_date / completion_date
// fields on the project record -- the backend currently returns none of
// these (confirmed against lib/normalizers.js). Dates below are
// deterministically derived from the project's own ID (not random) so
// the same project always shows the same placeholder dates across
// reloads, but they are NOT real sanction/completion dates.
export function placeholderLifecycleDates(projectId) {
  let hash = 0
  for (let i = 0; i < (projectId || '').length; i++) hash = (hash * 31 + projectId.charCodeAt(i)) >>> 0
  const baseYear = 2023 + (hash % 3)
  const baseMonth = hash % 12
  const day = 3 + (hash % 24)
  const start = new Date(baseYear, baseMonth, day)
  const addDays = n => { const d = new Date(start); d.setDate(d.getDate() + n); return d }
  const fmt = d => d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  return {
    recommended: fmt(start),
    sanctioned: fmt(addDays(45 + (hash % 30))),
    expenditureBegins: fmt(addDays(80 + (hash % 30))),
    completed: fmt(addDays(240 + (hash % 90))),
  }
}