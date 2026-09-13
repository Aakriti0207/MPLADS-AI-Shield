import React, { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Building2, ClipboardList, Landmark, Loader2, LockKeyhole, ShieldCheck, User } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const ROLE_OPTIONS = [
  { key: 'ministry', label: 'Ministry / Admin', icon: Landmark },
  { key: 'mp', label: 'Member of Parliament', icon: User },
  { key: 'state', label: 'State Nodal Authority', icon: Building2 },
  { key: 'district', label: 'District Authority', icon: ClipboardList },
]

export default function Login() {
  const [selectedRole, setSelectedRole] = useState('ministry')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)

  const { login, enterDemo, demoModeEnabled } = useAuth()
  const nav = useNavigate()
  const location = useLocation()
  const redirectTo = location.state?.from?.pathname || '/dashboard'

  useEffect(() => {
    document.title = 'MPLADS AI Shield | Secure Access'
  }, [])

  function validate() {
    const errors = {}
    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      errors.email = 'Email is required.'
    } else if (!EMAIL_PATTERN.test(trimmedEmail)) {
      errors.email = 'Enter a valid email address.'
    }
    if (!password) {
      errors.password = 'Password is required.'
    }
    return errors
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFormError('')

    const errors = validate()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setLoading(true)
    try {
      await login(email.trim(), password)
      nav(redirectTo, { replace: true })
    } catch (err) {
      if (err.status === 401) {
        setFormError('Incorrect email or password.')
      } else if (err.status === 422) {
        setFormError('Please check your email and password and try again.')
      } else if (err.status === null) {
        setFormError('Unable to reach the server. Check that the backend is running and try again.')
      } else {
        setFormError('Something went wrong. Please try again in a moment.')
      }
    } finally {
      setLoading(false)
    }
  }

  function handleDemoEntry() {
    if (enterDemo(selectedRole)) nav('/dashboard', { replace: true })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-panel p-4">
      <form onSubmit={handleSubmit} className="card w-full max-w-[420px] p-7" noValidate>
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-8 h-8 rounded-md flex items-center justify-center bg-navy text-white">
            <ShieldCheck size={17} aria-hidden="true" />
          </div>
          <span className="text-[15px] font-bold text-navy">MPLADS AI Shield</span>
        </div>
        <p className="text-xs text-muted mb-5">Secure access for authorized stakeholders</p>

        {demoModeEnabled && (
          <div className="mb-5 rounded-md border border-line bg-panel p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-semibold text-ink">Enter Demo Mode</div>
                <p className="text-[11px] text-muted mt-0.5">Frontend demonstration session; no credentials required.</p>
              </div>
              <button type="button" onClick={handleDemoEntry} className="btn-primary shrink-0 px-3 py-1.5 text-xs">
                Enter demo
              </button>
            </div>
          </div>
        )}

        <div className="text-[11px] font-medium text-muted mb-1.5">Select your role</div>
        <div className="grid grid-cols-2 gap-2 mb-4">
          {ROLE_OPTIONS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              aria-pressed={selectedRole === key}
              onClick={() => setSelectedRole(key)}
              disabled={loading}
              className="flex items-center gap-2 px-2.5 py-2 rounded-md border text-left transition disabled:opacity-60"
              style={{
                borderColor: selectedRole === key ? '#0b2e4f' : '#dce2e8',
                backgroundColor: selectedRole === key ? '#eef3f8' : '#ffffff',
              }}
            >
              <Icon size={14} className="shrink-0 text-navy" aria-hidden="true" />
              <span className="text-[11.5px] font-medium text-ink leading-tight">{label}</span>
            </button>
          ))}
        </div>

        {formError && (
          <div role="alert" className="mb-4 text-sm rounded-md p-3 bg-bad-bg" style={{ color: '#c0392b' }}>
            {formError}
          </div>
        )}

        <label className="block text-xs font-medium text-muted">Official Email / User ID</label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="mt-1.5 w-full border border-line rounded-md px-3 py-2.5 text-[13px] outline-none focus:border-navy"
          placeholder="name@mospi.gov.in"
          disabled={loading}
          autoComplete="username"
        />
        {fieldErrors.email && <p className="text-xs mt-1" style={{ color: '#c0392b' }}>{fieldErrors.email}</p>}

        <label className="block text-xs font-medium text-muted mt-4">Password</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="mt-1.5 w-full border border-line rounded-md px-3 py-2.5 text-[13px] outline-none focus:border-navy"
          placeholder="••••••••"
          disabled={loading}
          autoComplete="current-password"
        />
        {fieldErrors.password && <p className="text-xs mt-1" style={{ color: '#c0392b' }}>{fieldErrors.password}</p>}

        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full mt-6 disabled:opacity-70"
        >
          {loading && <Loader2 size={15} className="animate-spin" aria-hidden="true" />}
          {loading ? 'Signing in…' : 'Sign In'}
        </button>

        <Link to="/" className="block mt-2.5 text-center text-xs font-medium text-muted hover:text-navy">
          Back to public portal
        </Link>

        <p className="text-[10.5px] text-muted mt-4 text-center leading-4">
          <LockKeyhole size={10} className="inline -mt-0.5 mr-1" aria-hidden="true" />
          Access is restricted to registered monitoring-workspace accounts.
        </p>
      </form>
    </div>
  )
}