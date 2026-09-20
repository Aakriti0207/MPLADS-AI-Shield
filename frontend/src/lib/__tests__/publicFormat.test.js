import { describe, expect, it } from 'vitest'
import { cleanAgency, clampPercent, formatDateLong, formatInr, formatPercent, showInr, titleCase, NOT_AVAILABLE } from '../publicFormat'

describe('publicFormat', () => {
  it('formats rupees in Indian units', () => {
    expect(formatInr(12345678)).toBe('₹1.23 Cr')
    expect(formatInr(450000)).toBe('₹4.50 Lakh')
    expect(formatInr(9500)).toBe('₹9,500')
    expect(formatInr(23048672771.58)).toBe('₹2,304.87 Cr')
  })
  it('never turns missing values into 0 / NaN / undefined', () => {
    for (const v of [null, undefined, '', 'abc', NaN]) {
      expect(formatInr(v)).toBeNull()
      expect(formatPercent(v)).toBeNull()
      expect(showInr(v)).toBe(NOT_AVAILABLE)
    }
    expect(formatDateLong(null)).toBeNull()
    expect(formatDateLong('not a date')).toBeNull()
  })
  it('keeps a real zero as zero', () => {
    expect(formatInr(0)).toBe('₹0')
  })
  it('title-cases shouted district names', () => {
    expect(titleCase('SAMASTIPUR')).toBe('Samastipur')
    expect(titleCase('NORTH AND MIDDLE ANDAMAN')).toBe('North and Middle Andaman')
    expect(titleCase(null)).toBeNull()
  })
  it('cleans agency labels', () => {
    expect(cleanAgency('LATUR(DISTRICT COLLECTOR LATUR_IDA)')).toBe('Latur (District Collector Latur)')
  })
  it('clamps bar width but not the value', () => {
    expect(clampPercent(140)).toBe(100)
    expect(clampPercent(-3)).toBe(0)
    expect(clampPercent(null)).toBeNull()
  })
})