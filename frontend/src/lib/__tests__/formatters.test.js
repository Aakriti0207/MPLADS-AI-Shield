import { describe, expect, it } from 'vitest'
import { formatCurrency, formatPercent, formatRiskLevel, toNumber } from '../formatters'

describe('formatters', () => {
  it('preserves missing numeric values', () => {
    expect(toNumber(null)).toBeNull()
    expect(formatCurrency(null)).toBe('Not available')
  })

  it('formats backend risk and numeric values without changing meaning', () => {
    expect(formatRiskLevel('CRITICAL')).toBe('Critical')
    expect(formatPercent(68.4)).toBe('68%')
    expect(formatCurrency(10000000)).toBe('₹1.00 Cr')
  })
})
