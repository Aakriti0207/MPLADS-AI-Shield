export function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

// Indian-style magnitude formatting:
//   < ₹1,00,000        -> "₹12,345"     (plain rupees, grouped)
//   ₹1,00,000 - <1 Cr  -> "₹1.25 Lakh"
//   >= ₹1,00,00,000    -> "₹1.52 Cr"
// Previously this always divided by 1 crore, so a ₹14,84,933 sanction
// showed as the confusing "₹0.15 Cr" instead of "₹14.85 Lakh".
export function formatCurrency(value) {
  const number = toNumber(value)
  if (number === null) return 'Not available'
  const sign = number < 0 ? '-' : ''
  const abs = Math.abs(number)
  if (abs >= 10000000) {
    return `${sign}₹${(abs / 10000000).toFixed(2)} Cr`
  }
  if (abs >= 100000) {
    return `${sign}₹${(abs / 100000).toFixed(2)} Lakh`
  }
  return `${sign}₹${Math.round(abs).toLocaleString('en-IN')}`
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