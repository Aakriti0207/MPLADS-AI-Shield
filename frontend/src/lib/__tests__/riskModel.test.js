import { describe, expect, it } from 'vitest'
import {
  buildDataQuality,
  buildReviewChecklist,
  buildRiskModel,
  extractPeerComparisons,
  peerCriteria,
} from '../riskModel'

/* ==========================================================================
   Risk display-model tests.

   These guard the one property the whole Explainable AI page depends on:
   what the UI shows must reconcile with what the backend computed, and a
   missing signal must never be presentable as a clean signal.
   ========================================================================== */

// A payload shaped exactly like GET /projects/:id/risk, using the real caps
// from ml/risk_config.py (28/20/12/12/8/10/10 = 100).
function payload(overrides = {}) {
  return {
    work_id: 'WS/MP171/2024-2025/144805',
    risk_score: 49.73,
    risk_level: 'MEDIUM',
    evidence_status: 'SUFFICIENT',
    total_evidence_signals: 10,
    risk_reasons: ['Compliance reason', 'Financial reason'],
    components: {
      compliance: {
        label: 'Compliance',
        score: 28.6,
        weight: 28,
        contribution: 8,
        status: 'MEDIUM',
        reasons: ['Sanction was issued 81 days after recommendation.'],
        evidence: [{ rule_id: 'C01', severity: 'WARNING' }],
        description: 'Deterministic rule checks.',
        review_actions: ['Open the flagged rule(s).'],
      },
      financial_anomaly: {
        label: 'Financial Anomaly',
        score: 90,
        weight: 20,
        contribution: 18,
        status: 'HIGH',
        reasons: ['Expenditure-to-sanction ratio is unusually low.'],
        evidence: [
          {
            metric: 'total_expenditure',
            observed_display: '\u20b99,73,481',
            peer_median_display: '\u20b96,80,000',
            peer_deviation_pct: 43.2,
            peer_group_size: 124,
            peer_group_level: 'state_work_category',
            peer_group_key: 'Telangana|Normal/Others',
            modified_z_score: 5.58,
          },
        ],
        description: 'Peer-relative amount comparison.',
        review_actions: ['Verify expenditure against sanctioned estimates.'],
      },
      timeline_anomaly: {
        label: 'Timeline Anomaly',
        score: 50,
        weight: 12,
        contribution: 6,
        status: 'HIGH',
        reasons: ['Sanction-to-completion duration is unusually high.'],
        // Log-scaled peer stats: the backend deliberately omits a deviation %.
        evidence: [
          {
            metric: 'sanction_to_completion_days',
            observed_display: '406 days',
            peer_median_display: '180 days',
            peer_group_size: 98,
            peer_group_level: 'state_work_category',
            peer_group_key: 'Telangana|Normal/Others',
            modified_z_score: 10.28,
            peer_comparison_note: 'Peer statistics are on a log scale.',
          },
        ],
        description: 'Peer-relative duration comparison.',
        review_actions: ['Confirm the recorded dates.'],
      },
      duplicate: {
        label: 'Duplicate / Similar Work',
        score: 0,
        weight: 12,
        contribution: 0,
        status: 'NONE',
        reasons: [],
        evidence: [],
        description: 'Similar-work detection.',
        review_actions: ['Open the matched work ID(s).'],
      },
      data_quality: {
        label: 'Data Quality',
        score: 100,
        weight: 8,
        contribution: 8,
        status: 'LOW',
        reasons: ['Source fields conflict and require data-quality review.'],
        evidence: [{ rule_id: 'DQ01' }],
        description: 'Source/field conflicts.',
        review_actions: ['Reconcile the conflicting fields.'],
      },
      payment: {
        label: 'Payment Pattern',
        score: 12,
        weight: 10,
        contribution: 1.2,
        status: 'LOW',
        reasons: ['Payment utilisation ratio is unusually low.'],
        evidence: [{ signal: 'payment_utilization_ratio' }],
        description: 'Payment-pattern analysis.',
        review_actions: ['Review the individual payment transactions.'],
      },
      isolation_forest: {
        label: 'Statistical Outlier (Isolation Forest)',
        score: 85.3,
        weight: 10,
        contribution: 8.53,
        status: 'HIGH',
        reasons: ['Project is unusual relative to the fitted distribution.'],
        evidence: [{ strength: 'strong' }],
        description: 'Multivariate outlier detection.',
        review_actions: ['Treat this as a prioritisation hint.'],
      },
    },
    data_quality_notes: [],
    data_quality_detail_available: true,
    ...overrides,
  }
}

describe('buildRiskModel', () => {
  it('returns null when there is no payload at all', () => {
    expect(buildRiskModel(null)).toBeNull()
    expect(buildRiskModel(undefined)).toBeNull()
  })

  it('reconciles: contributions sum to the backend risk score', () => {
    const model = buildRiskModel(payload())
    expect(model.totalContribution).toBeCloseTo(49.73, 2)
    expect(model.score).toBe(49.73)
    expect(model.reconciles).toBe(true)
  })

  it('keeps raw score, weight and contribution as three separate quantities', () => {
    const model = buildRiskModel(payload())
    const financial = model.components.find(c => c.name === 'financial_anomaly')

    expect(financial.rawScore).toBe(90)
    expect(financial.weight).toBe(20)
    expect(financial.contribution).toBe(18)
    // The backend identity holds: raw x weight / 100 === contribution.
    expect((financial.rawScore * financial.weight) / 100).toBeCloseTo(financial.contribution, 2)
  })

  it('never lets weight percent be mistaken for share of final risk', () => {
    const model = buildRiskModel(payload())
    const financial = model.components.find(c => c.name === 'financial_anomaly')

    // Weight is 20%, but its share of the 49.73 contributed points is ~36.2%.
    expect(financial.weight).toBe(20)
    expect(financial.sharePct).toBeCloseTo((18 / 49.73) * 100, 1)
    expect(financial.sharePct).not.toBeCloseTo(financial.weight, 1)
  })

  it('flags when the backend numbers do not reconcile instead of hiding it', () => {
    const model = buildRiskModel(payload({ risk_score: 61 }))
    expect(model.reconciles).toBe(false)
  })

  it('separates triggered from evaluated-but-not-triggered components', () => {
    const model = buildRiskModel(payload())

    expect(model.triggered.map(c => c.name)).toEqual([
      'financial_anomaly',
      'isolation_forest',
      'compliance',
      'data_quality',
      'timeline_anomaly',
      'payment',
    ])
    expect(model.notTriggered.map(c => c.name)).toEqual(['duplicate'])
  })

  it('orders triggered components by real contribution, highest first', () => {
    const model = buildRiskModel(payload())
    const contributions = model.triggered.map(c => c.contribution)
    expect(contributions).toEqual([...contributions].sort((a, b) => b - a))
    expect(model.triggered[0].name).toBe('financial_anomaly')
  })

  it('handles the no-anomaly case without inventing signals', () => {
    const clean = payload({
      risk_score: 0,
      risk_level: 'LOW',
      total_evidence_signals: 0,
      components: Object.fromEntries(
        Object.entries(payload().components).map(([name, detail]) => [
          name,
          { ...detail, score: 0, contribution: 0, status: 'NONE', reasons: [], evidence: [] },
        ])
      ),
    })

    const model = buildRiskModel(clean)
    expect(model.triggered).toHaveLength(0)
    expect(model.notTriggered).toHaveLength(7)
    expect(model.totalContribution).toBe(0)
    expect(model.reconciles).toBe(true)
  })

  it('preserves legacy flat reasons so the WHY panel can never be empty', () => {
    const model = buildRiskModel(payload({ components: {} }))
    expect(model.hasComponents).toBe(false)
    expect(model.legacyReasons).toEqual(['Compliance reason', 'Financial reason'])
  })

  it('marks evidence as unavailable rather than absent when the backend says so', () => {
    const legacy = payload()
    legacy.components.payment.evidence = []
    legacy.components.payment.evidence_available = false

    const model = buildRiskModel(legacy)
    const payment = model.components.find(c => c.name === 'payment')

    expect(payment.evidenceAvailable).toBe(false)
    // The reasons are still real and still shown.
    expect(payment.reasons).toHaveLength(1)
  })

  it('still surfaces a component the frontend does not know about', () => {
    const future = payload()
    future.components.some_new_detector = {
      label: 'Some New Detector',
      score: 0,
      weight: 0,
      contribution: 0,
      status: 'NONE',
      reasons: [],
      evidence: [],
    }

    const model = buildRiskModel(future)
    expect(model.components.map(c => c.name)).toContain('some_new_detector')
  })
})

describe('buildDataQuality', () => {
  it('reports every domain as available when nothing is missing', () => {
    const quality = buildDataQuality(payload())
    expect(quality.complete).toBe(true)
    expect(quality.domains.every(d => d.evaluable === true)).toBe(true)
  })

  it('marks a named domain as unevaluable', () => {
    const quality = buildDataQuality(payload({ data_quality_notes: ['Payment pattern data'] }))
    const payment = quality.domains.find(d => d.label === 'Payment pattern data')

    expect(payment.evaluable).toBe(false)
    expect(quality.complete).toBe(false)
  })

  it('reports unknown, never "available", when detail was not recorded', () => {
    const quality = buildDataQuality(
      payload({ data_quality_notes: [], data_quality_detail_available: false })
    )

    expect(quality.detailAvailable).toBe(false)
    expect(quality.complete).toBe(false)
    // The critical assertion: missing detail must not read as a clean result.
    expect(quality.domains.every(d => d.evaluable === null)).toBe(true)
  })
})

describe('extractPeerComparisons', () => {
  it('only produces rows for signals that actually carry peer statistics', () => {
    const model = buildRiskModel(payload())
    const rows = extractPeerComparisons(model.components)

    expect(rows).toHaveLength(2)
    expect(rows.map(r => r.metric)).toEqual([
      'total_expenditure',
      'sanction_to_completion_days',
    ])
  })

  it('does not substitute a percentage when the backend omitted one', () => {
    const model = buildRiskModel(payload())
    const rows = extractPeerComparisons(model.components)
    const timeline = rows.find(r => r.metric === 'sanction_to_completion_days')

    expect(timeline.deviationPct).toBeNull()
    expect(timeline.zScore).toBeCloseTo(10.28, 2)
  })

  it('returns nothing when no peer data exists', () => {
    const noPeers = payload()
    Object.values(noPeers.components).forEach(detail => {
      detail.evidence = []
    })
    expect(extractPeerComparisons(buildRiskModel(noPeers).components)).toEqual([])
  })

  it('derives peer criteria from the group the backend actually used', () => {
    const rows = extractPeerComparisons(buildRiskModel(payload()).components)
    expect(peerCriteria(rows)).toEqual([
      'state work category',
      'Telangana',
      'Normal/Others',
    ])
  })
})

describe('buildReviewChecklist', () => {
  it('lists each action once, ordered by contribution', () => {
    const model = buildRiskModel(payload())
    const checklist = buildReviewChecklist(model.triggered)

    expect(checklist[0].componentLabel).toBe('Financial Anomaly')
    expect(new Set(checklist.map(i => i.action)).size).toBe(checklist.length)
  })

  it('is empty when nothing triggered', () => {
    expect(buildReviewChecklist([])).toEqual([])
  })
})