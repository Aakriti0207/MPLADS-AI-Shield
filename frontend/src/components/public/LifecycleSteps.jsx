import React from 'react'
import { ArrowRight, ArrowDown } from 'lucide-react'

// Each step maps onto a stage the source records actually carry:
// recommendation date, sanction (amount + date), implementing agency,
// expenditure records, completion record. No legal claims are added.
const STEPS = [
  { title: 'MP recommends', text: 'A Member of Parliament recommends a development work for their area.' },
  { title: 'Work is sanctioned', text: 'The work is approved and an amount is sanctioned for it.' },
  { title: 'Agency executes', text: 'An implementing agency carries out the work.' },
  { title: 'Funds are used', text: 'Payments made for the work are recorded as expenditure.' },
  { title: 'Project is completed', text: 'A completion record is entered once the work is finished.' },
]

// Decorative-only accent walking the stages from "recorded" (blue) to
// "recorded and spent" (teal/green) -- five distinct tones, none of
// them re-used elsewhere as a status colour, so this never competes
// with the semantic status pills used on project cards.
const STEP_ACCENT = ['border-t-info', 'border-t-teal', 'border-t-indigo', 'border-t-warn', 'border-t-good']

export default function LifecycleSteps() {
  return (
    <ol className="grid gap-3 md:grid-cols-5 md:gap-2 items-stretch">
      {STEPS.map((step, index) => (
        <li key={step.title} className="relative">
          <div className={`pub-card p-4 h-full border-t-[3px] ${STEP_ACCENT[index]}`}>
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-navy text-white text-[14px] font-bold" aria-hidden="true">
              {index + 1}
            </span>
            <h3 className="mt-3 text-[15.5px] font-semibold text-navy">
              <span className="sr-only">Step {index + 1}: </span>{step.title}
            </h3>
            <p className="mt-1 text-[13.5px] text-muted leading-snug">{step.text}</p>
          </div>
          {index < STEPS.length - 1 && (
            <>
              <ArrowRight size={16} className="hidden md:block absolute top-1/2 -right-[13px] -translate-y-1/2 text-blue z-10 bg-panel rounded-full" aria-hidden="true" />
              <ArrowDown size={16} className="md:hidden mx-auto mt-1 text-blue" aria-hidden="true" />
            </>
          )}
        </li>
      ))}
    </ol>
  )
}