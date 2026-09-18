import React, { useEffect, useState } from 'react'
import { fetchRoleDashboard } from '../../features/dashboard/api'
import { ROLE } from '../../lib/roles'
import { useAuth } from '../../context/AuthContext'
import LoadingState from '../ui/LoadingState'
import ErrorState from '../ui/ErrorState'
import ScopeBanner from '../layout/ScopeBanner'
import MpDashboard from './MpDashboard'
import StateDashboard from './StateDashboard'
import DistrictDashboard from './DistrictDashboard'

/**
 * Router for the three jurisdictional dashboards.
 *
 * What changed, and why it matters
 * --------------------------------
 * The previous version of this component fetched a page of projects and
 * filtered them in React against a jurisdiction the USER picked from a
 * dropdown. That was a preview, not access control: the data had already
 * crossed the wire, and the "scope" was whatever the officer selected.
 *
 * Now the backend decides. GET /dashboard/role-overview returns figures
 * already aggregated over the authenticated account's authorized
 * records, plus the scope it used. There is no jurisdiction selector
 * here, because there is no jurisdiction to select -- an officer has
 * exactly one, and it is assigned, not chosen.
 *
 * The `dashboard` key in the response (not the local role guess) picks
 * the component, so the backend and the UI cannot disagree about which
 * cockpit an account gets.
 */
export default function ScopedDashboard({ role: roleProp }) {
  const { isDemo, role: sessionRole } = useAuth()
  const role = roleProp || sessionRole

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetchRoleDashboard()
      .then(payload => { if (!cancelled) setData(payload) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to reach the API') })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [role])

  if (loading) return <LoadingState text="Loading your scoped dashboard…" />
  if (error) return <ErrorState title="Could not load your dashboard" message={error} />
  if (!data) return null

  // No jurisdiction assigned: say so plainly rather than rendering a
  // grid of zeroes, which would read as "your district has no projects".
  if (data.scope_available === false) {
    return <UnassignedScope data={data} />
  }

  const key = data.dashboard || DASHBOARD_BY_ROLE[role] || 'unscoped'

  if (key === 'mp') return <MpDashboard data={data} />
  if (key === 'state') return <StateDashboard data={data} />
  if (key === 'district') return <DistrictDashboard data={data} />

  return <UnassignedScope data={data} />
}

const DASHBOARD_BY_ROLE = {
  [ROLE.MP]: 'mp',
  [ROLE.STATE_NODAL]: 'state',
  [ROLE.DISTRICT_AUTHORITY]: 'district',
}

function UnassignedScope({ data }) {
  return (
    <div>
      <header className="mb-4">
        <h1 className="text-[19px] font-semibold text-ink">
          {data.role_label || 'Overview'}
        </h1>
        <p className="text-[13px] text-muted mt-0.5">
          This view shows only records the backend authorizes for your account.
        </p>
      </header>

      <ScopeBanner scope={data.scope} />

      <div className="card p-8 text-center">
        <p className="text-[13px] text-ink font-medium">No jurisdiction assigned</p>
        <p className="text-[12.5px] text-muted mt-1.5 max-w-lg mx-auto">
          {data.unavailable_reason
            || data.empty_state_message
            || 'No state, district or constituency has been assigned to this account, so no project records are authorized for it yet.'}
        </p>
        <p className="text-[12px] text-muted mt-3">
          A Ministry administrator can assign one; jurisdictions are never
          self-selected.
        </p>
      </div>
    </div>
  )
}