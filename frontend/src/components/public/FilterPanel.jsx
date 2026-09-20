import React, { useEffect, useRef, useState } from 'react'
import { SlidersHorizontal, X } from 'lucide-react'
import { formatCount, titleCase } from '../../lib/publicFormat'

const EMPTY = { state: '', district: '', category: '', status: '', year: '' }

export function activeFilterCount(value) {
  return ['state', 'district', 'category', 'status', 'year'].filter(key => value[key]).length
}

function Field({ id, label, value, onChange, disabled, children }) {
  return (
    <div>
      <label htmlFor={id} className="pub-label">{label}</label>
      <select id={id} className="pub-input" value={value} disabled={disabled} onChange={event => onChange(event.target.value)}>
        {children}
      </select>
    </div>
  )
}

function Fields({ idPrefix, draft, setDraft, options, onDraftStateChange }) {
  const opt = (list, format = v => v) =>
    list.map(o => <option key={o.value} value={o.value}>{format(o.value)} ({formatCount(o.count)})</option>)

  return (
    <div className="grid gap-4">
      <Field id={`${idPrefix}-state`} label="State" value={draft.state}
        onChange={state => { setDraft({ ...draft, state, district: '' }); onDraftStateChange(state) }}>
        <option value="">All states</option>
        {opt(options.states)}
      </Field>
      <Field id={`${idPrefix}-district`} label="District" value={draft.district}
        disabled={!draft.state} onChange={district => setDraft({ ...draft, district })}>
        <option value="">{draft.state ? 'All districts' : 'Choose a state first'}</option>
        {opt(options.districts, titleCase)}
      </Field>
      <Field id={`${idPrefix}-status`} label="Project status" value={draft.status}
        onChange={status => setDraft({ ...draft, status })}>
        <option value="">All statuses</option>
        {opt(options.statuses)}
      </Field>
      <Field id={`${idPrefix}-category`} label="Work category" value={draft.category}
        onChange={category => setDraft({ ...draft, category })}>
        <option value="">All categories</option>
        {opt(options.categories)}
      </Field>
      <Field id={`${idPrefix}-year`} label="Sanction year" value={draft.year}
        onChange={year => setDraft({ ...draft, year })}>
        <option value="">Any year</option>
        {opt(options.years)}
      </Field>
    </div>
  )
}

/**
 * Filters: State, District, Status, Category, Sanction year.
 * Only options that exist in the data are offered (from
 * /public/explorer/filters). Changes are staged and committed with
 * [Apply Filters]. On small screens the same form opens as a bottom
 * sheet behind a [Filters] button.
 */
export default function FilterPanel({ value, options, onApply, onDraftStateChange = () => {}, className = '' }) {
  const [draft, setDraft] = useState({ ...EMPTY, ...value })
  const [sheetOpen, setSheetOpen] = useState(false)
  const sheetRef = useRef(null)

  // Keep the staged form in sync when filters change from outside
  // (e.g. "Clear all", browser back, or a deep link).
  useEffect(() => { setDraft({ ...EMPTY, ...value }) }, [value.state, value.district, value.category, value.status, value.year])

  useEffect(() => {
    if (!sheetOpen) return undefined
    sheetRef.current?.focus()
    const onKey = event => { if (event.key === 'Escape') setSheetOpen(false) }
    window.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [sheetOpen])

  const applied = activeFilterCount(value)

  function apply() {
    onApply({ ...EMPTY, ...draft })
    setSheetOpen(false)
  }

  function clear() {
    setDraft(EMPTY)
    onDraftStateChange('')
    onApply(EMPTY)
    setSheetOpen(false)
  }

  const actions = (
    <div className="flex gap-2 mt-5">
      <button type="button" className="pub-btn-primary flex-1 !px-2 whitespace-nowrap" onClick={apply}>Apply Filters</button>
      <button type="button" className="pub-btn-secondary flex-1 !px-2 whitespace-nowrap" onClick={clear}>Clear Filters</button>
    </div>
  )

  return (
    <div className={className}>
      <button
        type="button"
        className="pub-btn-secondary lg:hidden w-full"
        onClick={() => setSheetOpen(true)}
        aria-haspopup="dialog"
      >
        <SlidersHorizontal size={16} aria-hidden="true" />
        Filters{applied ? ` (${applied})` : ''}
      </button>

      <div className="hidden lg:block pub-card p-5">
        <h2 className="text-[16px] font-bold text-navy mb-4 flex items-center gap-2">
          <SlidersHorizontal size={16} aria-hidden="true" /> Filters
        </h2>
        <Fields idPrefix="f-desktop" draft={draft} setDraft={setDraft} options={options} onDraftStateChange={onDraftStateChange} />
        {actions}
      </div>

      {sheetOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Filters">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSheetOpen(false)} aria-hidden="true" />
          <div ref={sheetRef} tabIndex={-1} className="absolute inset-x-0 bottom-0 max-h-[88vh] overflow-y-auto bg-white rounded-t-2xl p-5 shadow-2xl outline-none">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[18px] font-bold text-navy">Filters</h2>
              <button type="button" onClick={() => setSheetOpen(false)} aria-label="Close filters" className="w-11 h-11 inline-flex items-center justify-center rounded-lg border border-line">
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <Fields idPrefix="f-mobile" draft={draft} setDraft={setDraft} options={options} onDraftStateChange={onDraftStateChange} />
            {actions}
          </div>
        </div>
      )}
    </div>
  )
}