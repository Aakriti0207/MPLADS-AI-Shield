// Sidebar nav entries now live in app/routes.jsx (single source of truth
// for routing + shell chrome). This file keeps only the shared `money`
// formatter still used by ProjectDetails/Reports.
export const money = value => `₹${(value / 10000000).toFixed(2)} Cr`
