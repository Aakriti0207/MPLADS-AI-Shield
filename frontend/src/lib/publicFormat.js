import { toNumber } from './formatters'

/**
 * Citizen-facing formatting helpers for the public portal.
 *
 * Rule: a value that is genuinely missing is returned as `null` by the
 * `format*` functions so callers can decide what to show. The `show*`
 * variants return a readable fallback ("Not available") and are what the
 * UI normally uses -- so the portal never prints "undefined", "null",
 * "NaN" or a misleading "0" for data that simply is not recorded.
 */

export const NOT_AVAILABLE = 'Not available'

const IN = 'en-IN'

/** ₹ amounts in Indian units: ₹1,234 / ₹4.50 Lakh / ₹12.34 Cr. */
export function formatInr(value) {
  const number = toNumber(value)
  if (number === null) return null
  const abs = Math.abs(number)
  if (abs >= 1e7) return `₹${(number / 1e7).toLocaleString(IN, { maximumFractionDigits: 2, minimumFractionDigits: 2 })} Cr`
  if (abs >= 1e5) return `₹${(number / 1e5).toLocaleString(IN, { maximumFractionDigits: 2, minimumFractionDigits: 2 })} Lakh`
  return `₹${number.toLocaleString(IN, { maximumFractionDigits: 0 })}`
}

/** Exact rupee figure, for tooltips / detail pages: ₹12,34,567. */
export function formatInrExact(value) {
  const number = toNumber(value)
  if (number === null) return null
  return `₹${number.toLocaleString(IN, { maximumFractionDigits: 0 })}`
}

export function formatCount(value) {
  const number = toNumber(value)
  return number === null ? null : number.toLocaleString(IN)
}

export function formatPercent(value, digits = 0) {
  const number = toNumber(value)
  if (number === null) return null
  return `${number.toLocaleString(IN, { maximumFractionDigits: digits, minimumFractionDigits: 0 })}%`
}

const DATE_FMT = { day: 'numeric', month: 'short', year: 'numeric' }

/** ISO date (YYYY-MM-DD) or timestamp -> "12 Feb 2024". */
export function formatDateLong(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString('en-IN', DATE_FMT)
}

export function formatDateTime(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return `${date.toLocaleDateString('en-IN', DATE_FMT)}, ${date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}`
}

export const showInr = value => formatInr(value) ?? NOT_AVAILABLE
export const showCount = value => formatCount(value) ?? NOT_AVAILABLE
export const showPercent = (value, digits = 0) => formatPercent(value, digits) ?? NOT_AVAILABLE
export const showDate = value => formatDateLong(value) ?? NOT_AVAILABLE

const SMALL_WORDS = new Set(['and', 'of', 'the', 'in', 'on', 'at', 'for', 'to'])

/** "SAMASTIPUR" -> "Samastipur"; keeps small words lower-case. */
export function titleCase(value) {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  if (!text) return null
  return text
    .toLowerCase()
    .split(/(\s+|-|\/|\()/)
    .map((part, index) => {
      if (!part || /^(\s+|-|\/|\()$/.test(part)) return part
      if (index > 0 && SMALL_WORDS.has(part)) return part
      return part.charAt(0).toUpperCase() + part.slice(1)
    })
    .join('')
}

/** Source agency strings look like "LATUR(DISTRICT COLLECTOR LATUR_IDA)". */
export function cleanAgency(value) {
  if (!value) return null
  const text = String(value)
    .replace(/_IDA\b/gi, '')
    .replace(/\s*\(\s*/g, ' (')
    .replace(/\s+/g, ' ')
    .trim()
  return titleCase(text)
}

/** Pluralise a count word: pluralize(1, 'project') -> "1 project". */
export function pluralize(count, word) {
  const formatted = formatCount(count) ?? '0'
  return `${formatted} ${word}${Number(count) === 1 ? '' : 's'}`
}

/** Bar width helper: clamp a percentage to 0-100 (null -> null). */
export function clampPercent(value) {
  const number = toNumber(value)
  if (number === null) return null
  return Math.max(0, Math.min(100, number))
}