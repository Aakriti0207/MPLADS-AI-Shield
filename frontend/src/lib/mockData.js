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

// Used by: Home.jsx (public, unauthenticated state-wise map) and as a
// visual reference for state names/positions elsewhere.
// Needs: a real "/dashboard/by-state-geo" (or similar) endpoint
// returning { state, project_count, review_count } -- state names
// already exist per-project (normalizeProject().state), but there's no
// aggregated geo/tier endpoint yet.
export const STATE_STATS = [
  { name: 'Jammu & Kashmir', row: 1, col: 4, tier: 'low' },
  { name: 'Punjab', row: 2, col: 3, tier: 'low' },
  { name: 'Himachal Pradesh', row: 2, col: 4, tier: 'low' },
  { name: 'Uttarakhand', row: 2, col: 5, tier: 'low' },
  { name: 'Haryana', row: 3, col: 3, tier: 'medium' },
  { name: 'Delhi', row: 3, col: 4, tier: 'low' },
  { name: 'Uttar Pradesh', row: 3, col: 5, tier: 'medium' },
  { name: 'Assam', row: 3, col: 8, tier: 'medium' },
  { name: 'Rajasthan', row: 4, col: 2, tier: 'medium' },
  { name: 'Madhya Pradesh', row: 4, col: 4, tier: 'low' },
  { name: 'Bihar', row: 4, col: 6, tier: 'high' },
  { name: 'West Bengal', row: 4, col: 7, tier: 'medium' },
  { name: 'Gujarat', row: 5, col: 1, tier: 'low' },
  { name: 'Chhattisgarh', row: 5, col: 5, tier: 'low' },
  { name: 'Jharkhand', row: 5, col: 6, tier: 'medium' },
  { name: 'Odisha', row: 5, col: 7, tier: 'low' },
  { name: 'Maharashtra', row: 6, col: 3, tier: 'medium' },
  { name: 'Telangana', row: 6, col: 5, tier: 'low' },
  { name: 'Andhra Pradesh', row: 7, col: 5, tier: 'low' },
  { name: 'Karnataka', row: 7, col: 3, tier: 'low' },
  { name: 'Tamil Nadu', row: 8, col: 4, tier: 'low' },
  { name: 'Kerala', row: 8, col: 3, tier: 'low' },
]

// Used by: Home.jsx, only for anonymous (unauthenticated) visitors, since
// /dashboard/stats and /projects both require auth. Once a public,
// unauthenticated summary endpoint exists, this whole block can go and
// Home can always fetch real figures.
export const DEMO_PUBLIC_SNAPSHOT = {
  totalProjects: 43863,
  totalSanctioned: 23040000000, // paise-free rupee value, matches formatCurrency's /1e7 = ₹2,304 Cr
  totalExpenditure: 2080000000, // -> ₹208 Cr
  completedProjects: 22956,
  requiresReview: 1667,
  statusDistribution: [
    { name: 'Recommended', value: 5210 },
    { name: 'Sanctioned', value: 6890 },
    { name: 'Completed', value: 22956 },
    { name: 'Requires Review', value: 1667 },
  ],
  trend: [
    { month: 'Apr', expenditure: 96 }, { month: 'May', expenditure: 108 }, { month: 'Jun', expenditure: 121 },
    { month: 'Jul', expenditure: 133 }, { month: 'Aug', expenditure: 129 }, { month: 'Sep', expenditure: 148 },
    { month: 'Oct', expenditure: 156 }, { month: 'Nov', expenditure: 151 }, { month: 'Dec', expenditure: 163 },
    { month: 'Jan', expenditure: 172 }, { month: 'Feb', expenditure: 181 }, { month: 'Mar', expenditure: 208 },
  ],
  sampleProjects: [
    { id: 'WS/MP1042/2024-2025/017', state: 'Bihar', district: 'Muzaffarpur', mpName: 'R. K. Choudhary', workType: 'Health Infrastructure', sanctioned: 145000000, expenditure: 129000000, risk: 'High' },
    { id: 'WS/MP0512/2024-2025/003', state: 'Uttar Pradesh', district: 'Gorakhpur', mpName: 'S. N. Tiwari', workType: 'Road Infrastructure', sanctioned: 220000000, expenditure: 216000000, risk: 'Low' },
    { id: 'WS/MP0217/2024-2025/009', state: 'Rajasthan', district: 'Jodhpur', mpName: 'V. P. Rathore', workType: 'Street Lighting', sanctioned: 82000000, expenditure: 0, risk: 'Medium' },
    { id: 'WS/MP0876/2024-2025/021', state: 'West Bengal', district: 'Murshidabad', mpName: 'A. Halder', workType: 'Education Facility', sanctioned: 114000000, expenditure: 61000000, risk: 'Medium' },
    { id: 'WS/MP1298/2024-2025/005', state: 'Odisha', district: 'Cuttack', mpName: 'B. Mohanty', workType: 'Irrigation', sanctioned: 96000000, expenditure: 94000000, risk: 'Low' },
  ],
}

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