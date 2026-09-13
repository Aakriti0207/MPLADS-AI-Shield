import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, LockKeyhole, Loader2, ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)

  const { login } = useAuth()
  const nav = useNavigate()
  const location = useLocation()
  const redirectTo = location.state?.from?.pathname || '/dashboard'

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

  return (
    <div className="min-h-screen flex items-center justify-center bg-panel p-4">
      <div className="w-full max-w-[420px]">
        <Link to="/" className="text-sm text-muted inline-flex items-center gap-1.5 mb-4"><ArrowLeft size={14} /> Back to home</Link>

        <form onSubmit={handleSubmit} className="card p-7" noValidate>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-8 h-8 rounded-md flex items-center justify-center bg-navy text-white"><ShieldCheck size={16} /></div>
            <span className="text-[15px] font-bold text-navy">MPLADS Insight</span>
          </div>
          <p className="text-xs text-muted mb-5">Secure access for authorized stakeholders</p>

          {formError && (
            <div className="mb-4 text-sm rounded-md p-3 bg-bad-bg" style={{ color: '#c0392b' }}>
              {formError}
            </div>
          )}

          <label className="block text-xs font-medium text-muted">Official Email / User ID</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="mt-1.5 w-full border border-line rounded-md px-3 py-2.5 text-[13px] outline-none focus:border-navy"
            placeholder="you@mospi.gov.in"
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
            {loading && <Loader2 size={15} className="animate-spin" />}
            {loading ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="text-[10.5px] text-muted mt-4 text-center leading-4">
            <LockKeyhole size={10} className="inline -mt-0.5 mr-1" />
            Access is restricted to registered monitoring-workspace accounts.
          </p>
        </form>
      </div>
    </div>
  )
}