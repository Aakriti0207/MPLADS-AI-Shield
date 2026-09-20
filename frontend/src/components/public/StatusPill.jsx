import React from 'react'
import { statusStyle } from '../../lib/publicTheme'

/** Status = icon + word + tint. Never colour alone. */
export default function StatusPill({ status, size = 'md' }) {
  const label = status || 'Not specified'
  const style = statusStyle(label)
  const Icon = style.icon
  const pad = size === 'lg' ? 'px-3 py-1.5 text-[14px]' : 'px-2.5 py-1 text-[12.5px]'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${pad}`}
      style={{ color: style.text, backgroundColor: style.bg }}
      title={style.hint}
    >
      <Icon size={size === 'lg' ? 16 : 14} aria-hidden="true" />
      {label}
    </span>
  )
}