import React from 'react'
import { MapPin } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { scopeIndicator } from '../../lib/roles'

/**
 * The scope indicator every scoped view must display.
 *
 * Why this component exists at all: an officer looking at a total of
 * "1,408 projects" needs to know, without ambiguity, whether that is
 * their district, their state or the country. Getting this wrong is not
 * a cosmetic bug -- it is someone drawing a national conclusion from
 * district data, or the reverse.
 *
 * The sentence is taken from the BACKEND's own `scope.indicator`, which
 * describes what the API actually filtered on. It is never assembled
 * from a dropdown the user happened to pick, because only the server
 * knows what it really returned.
 *
 * Pass `scope` when a response carried its own scope block (that is the
 * most truthful source for that particular payload); otherwise it falls
 * back to the session's scope.
 */
export default function ScopeBanner({ scope, note, className = '' }) {
  const { scope: sessionScope, role } = useAuth()
  const effective = scope || sessionScope

  if (!effective) return null

  const unassigned = effective.type === 'none'

  return (
    <div
      className={`flex items-start gap-2 rounded-md border px-3 py-2 mb-4 ${className}`}
      style={
        unassigned
          ? { borderColor: '#DCE2E8', backgroundColor: '#F3F5F7' }
          : { borderColor: '#DCE2E8', backgroundColor: '#FFFFFF' }
      }
    >
      <MapPin size={14} className="mt-0.5 shrink-0 text-muted" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-[12.5px] font-medium text-ink">
          {scopeIndicator(effective, role)}
        </p>
        {note && <p className="text-[11.5px] text-muted mt-0.5">{note}</p>}
        {unassigned && !note && (
          <p className="text-[11.5px] text-muted mt-0.5">
            Contact the Ministry administrator to have a state, district or
            constituency assigned to this account.
          </p>
        )}
      </div>
    </div>
  )
}