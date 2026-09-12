import { describe, expect, it } from 'vitest'
import { normalizeProject, normalizeRisk, unwrapList } from '../normalizers'

describe('normalizers', () => {
  it('maps the project API contract and preserves nulls', () => {
    const project = normalizeProject({ project_id: 'P-1', risk_level: 'HIGH', sanctioned_amount: null })
    expect(project.id).toBe('P-1')
    expect(project.risk).toBe('High')
    expect(project.sanctioned).toBeNull()
  })

  it('normalizes Risk Fusion explanations without inventing evidence', () => {
    const risk = normalizeRisk({ work_id: 'P-1', risk_score: 42, risk_reasons: ['Review signal'] })
    expect(risk.workId).toBe('P-1')
    expect(risk.riskScore).toBe(42)
    expect(risk.reasons).toEqual(['Review signal'])
    expect(risk.evidence).toBeNull()
  })

  it('unwraps supported list response shapes', () => {
    expect(unwrapList({ projects: [{ project_id: 'P-1' }] })).toHaveLength(1)
    expect(unwrapList([])).toEqual([])
  })
})
