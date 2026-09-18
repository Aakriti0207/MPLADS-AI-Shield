import { describe, expect, it } from 'vitest'
import {
  normalizePublicDistrictResponse,
  normalizePublicInsights,
  normalizePublicOverview,
  normalizePublicProject,
  normalizePublicTrend,
} from '../publicNormalizers'

describe('normalizePublicProject', () => {
  it('maps the public-safe field set and preserves the canonical project id', () => {
    const result = normalizePublicProject({
      project_id: 'WS/MP1/2023-2024/103702',
      state: 'Bihar',
      district: 'PATNA',
      constituency: 'Patliputra',
      mp_name: 'Test MP',
      work_type: 'Road',
      implementing_agency: 'PWD',
      sanctioned_amount: '500000.00',
      expenditure: '400000.00',
      financial_progress: '80.00',
      status: 'Ongoing',
      sanction_date: '2023-04-01',
      actual_completion: null,
    })

    expect(result.id).toBe('WS/MP1/2023-2024/103702')
    expect(result.district).toBe('PATNA')
    expect(result.sanctioned).toBe(500000)
    expect(result.financialProgress).toBe(80)
    expect(result.sanctionDate).toBe('2023-04-01')
    expect(result.actualCompletion).toBeNull()
  })

  it('never emits a risk field even when the payload contains one', () => {
    const result = normalizePublicProject({
      project_id: 'WS/1',
      risk_score: 87.5,
      risk_level: 'CRITICAL',
      risk_reason_1: 'Expenditure exceeds sanctioned amount',
      duplicate_risk_score: 0.9,
      isolation_forest_score: 0.7,
      risk_metadata: { reviewer_notes: 'internal' },
    })

    const serialized = JSON.stringify(result)

    expect('riskScore' in result).toBe(false)
    expect('risk' in result).toBe(false)
    expect('raw' in result).toBe(false)
    expect(serialized).not.toContain('CRITICAL')
    expect(serialized).not.toContain('87.5')
    expect(serialized).not.toContain('reviewer_notes')
  })
})

describe('normalizePublicOverview', () => {
  it('drops risk_level_counts from the public overview payload', () => {
    const result = normalizePublicOverview({
      total_projects: 10,
      risk_level_counts: { LOW: 5, CRITICAL: 5 },
      recent_projects: [{ project_id: 'WS/1', risk_level: 'CRITICAL' }],
    })

    expect('risk_level_counts' in result).toBe(false)
    expect(JSON.stringify(result)).not.toContain('CRITICAL')
    expect(result.total_projects).toBe(10)
  })

  it('defaults the aggregate lists so the UI never reads undefined', () => {
    const result = normalizePublicOverview({})

    expect(result.by_state).toEqual([])
    expect(result.by_work_type).toEqual([])
    expect(result.status_distribution).toEqual([])
    expect(result.recent_projects).toEqual([])
  })
})

describe('normalizePublicTrend', () => {
  it('preserves hasRecords so "no records" is distinguishable from a real zero', () => {
    const result = normalizePublicTrend({
      points: [
        { period: '2025-01', label: 'Jan 2025', project_count: 4, amount: 1000, has_records: true },
        { period: '2025-02', label: 'Feb 2025', project_count: 0, amount: 0, has_records: false },
      ],
      basis: 'Attributed to the recorded date.',
      projects_with_data: 8950,
      total_projects: 43863,
      coverage_percent: 20.4,
    })

    expect(result.points[0].hasRecords).toBe(true)
    expect(result.points[1].hasRecords).toBe(false)
    expect(result.projectsWithData).toBe(8950)
    expect(result.coveragePercent).toBeCloseTo(20.4)
  })

  it('returns an empty series rather than inventing points when there is no data', () => {
    const result = normalizePublicTrend({})

    expect(result.points).toEqual([])
    expect(result.coveragePercent).toBeNull()
  })
})

describe('normalizePublicInsights', () => {
  const PAYLOAD = {
    kpis: {
      total_projects: 43863,
      total_sanctioned_amount: '23048672771.58',
      total_expenditure: '3849817769.00',
      completed_projects: 23283,
      active_works: 14537,
      status_not_specified: 6043,
      expenditure_utilisation_percent: '16.70',
      completion_rate_percent: '53.08',
      states_covered: 35,
      districts_covered: 735,
    },
    trends: {
      expenditure: { points: [], basis: 'x', projects_with_data: 0, total_projects: 0 },
      completion: { points: [], basis: 'y', projects_with_data: 0, total_projects: 0 },
      sanction: { points: [], basis: 'z', projects_with_data: 0, total_projects: 0 },
    },
    by_state: [
      {
        state: 'Maharashtra',
        district_count: 43,
        project_count: 1408,
        total_sanctioned_amount: '1101310138.00',
        total_expenditure: '433272104.00',
        completed_projects: 404,
        active_works: 525,
        expenditure_utilisation_percent: '39.34',
        completion_rate_percent: '28.69',
      },
    ],
    by_district: [
      {
        state: 'Maharashtra',
        district: 'MUMBAI SUBURBAN',
        project_count: 112,
        total_sanctioned_amount: '268300000.00',
        total_expenditure: '62429484.00',
        completed_projects: 0,
        active_works: 99,
        expenditure_utilisation_percent: '23.27',
        completion_rate_percent: '0.00',
      },
    ],
    by_work_type: [
      { work_type: 'Normal/Others', count: 37037, total_sanctioned_amount: '1.00', total_expenditure: '2.00' },
    ],
    status_distribution: [{ status: 'Completed', count: 23283 }],
    recent_projects: [{ project_id: 'WS/1' }],
    data_coverage: {
      fields: [
        { field: 'completion_date', projects_with_data: 22956, total_projects: 43863, coverage_percent: '52.33' },
      ],
      notes: ['Completion dates exist for 22,956 of 43,863 projects.'],
    },
    disclaimer: 'Aggregated from published MPLADS records.',
  }

  it('converts the public contract into numeric, camelCase UI data', () => {
    const result = normalizePublicInsights(PAYLOAD)

    expect(result.kpis.totalProjects).toBe(43863)
    expect(result.kpis.completedProjects).toBe(23283)
    expect(result.kpis.activeWorks).toBe(14537)
    expect(result.kpis.statusNotSpecified).toBe(6043)
    expect(result.kpis.districtsCovered).toBe(735)
    expect(result.byState[0].state).toBe('Maharashtra')
    expect(result.byState[0].projectCount).toBe(1408)
    expect(result.byState[0].districtCount).toBe(43)
    expect(result.byDistrict[0].district).toBe('MUMBAI SUBURBAN')
    expect(result.byWorkType[0].count).toBe(37037)
    expect(result.statusDistribution[0].status).toBe('Completed')
    expect(result.recentProjects[0].id).toBe('WS/1')
    expect(result.dataCoverage.notes).toHaveLength(1)
    expect(result.dataCoverage.fields[0].projectsWithData).toBe(22956)
  })

  it('tolerates an entirely empty payload without throwing', () => {
    const result = normalizePublicInsights({})

    expect(result.kpis.totalProjects).toBeNull()
    expect(result.byState).toEqual([])
    expect(result.byDistrict).toEqual([])
    expect(result.trends.expenditure.points).toEqual([])
    expect(result.dataCoverage.notes).toEqual([])
  })

  it('carries no risk/AI/investigation key through to the UI contract', () => {
    const result = normalizePublicInsights({
      ...PAYLOAD,
      risk_level_counts: { CRITICAL: 5 },
      by_state_risk: [{ state: 'Maharashtra', critical: 5 }],
      alerts: [{ id: 1, severity: 'CRITICAL' }],
    })

    const serialized = JSON.stringify(result)

    expect(serialized).not.toContain('CRITICAL')
    expect(serialized).not.toContain('risk')
    expect(serialized).not.toContain('alert')
  })
})

describe('normalizePublicDistrictResponse', () => {
  it('normalizes the drilldown payload', () => {
    const result = normalizePublicDistrictResponse({
      state: 'Bihar',
      districts: [
        {
          state: 'Bihar',
          district: 'PATNA',
          project_count: 50,
          total_sanctioned_amount: '100.00',
          total_expenditure: '40.00',
          completed_projects: 10,
          active_works: 40,
          expenditure_utilisation_percent: '40.00',
          completion_rate_percent: '20.00',
        },
      ],
    })

    expect(result.state).toBe('Bihar')
    expect(result.districts[0].district).toBe('PATNA')
    expect(result.districts[0].projectCount).toBe(50)
    expect(result.districts[0].utilisationPercent).toBe(40)
  })

  it('returns an empty district list when the payload has none', () => {
    expect(normalizePublicDistrictResponse({}).districts).toEqual([])
  })
})
