export function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function formatCurrency(value) {
  const number = toNumber(value)
  return number === null ? 'Not available' : `₹${(number / 10000000).toFixed(2)} Cr`
}

export function formatNumber(value) {
  const number = toNumber(value)
  return number === null ? 'Not available' : number.toLocaleString()
}

export function formatPercent(value) {
  const number = toNumber(value)
  return number === null ? 'Not available' : `${Math.round(number)}%`
}

export function formatDate(value) {
  if (!value) return 'Not available'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Not available' : date.toLocaleDateString('en-IN')
}

export function formatRiskLevel(value) {
  if (!value) return null
  return String(value).charAt(0).toUpperCase() + String(value).slice(1).toLowerCase()
}

export function formatStatus(value) {
  if (!value) return null
  return String(value).charAt(0).toUpperCase() + String(value).slice(1).toLowerCase()
}
