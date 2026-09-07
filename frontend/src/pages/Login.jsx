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

  return <div className="min-h-screen grid lg:grid-cols-2 bg-white">
    <div className="hidden lg:flex bg-[#082f57] text-white p-12 flex-col justify-between">
      <Link to="/" className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-white/10 flex items-center justify-center">
          <ShieldCheck/>
        </div>
        <b>MPLADS Insight</b>
      </Link>
      <div>
        <div className="eyebrow !text-blue-200">Secure workspace</div>
        <h1 className="text-4xl font-extrabold mt-3">Role-based access for project monitoring teams.</h1>
        <p className="text-blue-100 mt-5 max-w-md leading-7">The prototype separates public visibility from authenticated operational workflows. MPLADS Project Intelligence Platform
        Monitor projects. Identify risks. Improve transparency.
        AI-powered monitoring for smarter public infrastructure..</p>
      </div>
      <div className="text-xs text-blue-200">Sign in with your registered account</div>
    </div>
    <div className="flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <Link to="/" className="text-sm text-slate-500 inline-flex items-center gap-2 mb-8"><ArrowLeft size={15}/> Back to home</Link>
        <form onSubmit={handleSubmit} className="card p-7" noValidate>
          <div className="h-12 w-12 rounded-xl bg-blue-50 text-navy flex items-center justify-center"><LockKeyhole/></div>
          <h2 className="text-2xl font-extrabold mt-5">Sign in</h2>
          <p className="text-sm text-slate-500 mt-1">Access the monitoring workspace</p>

          {formError && (
            <div className="mt-5 text-sm text-rose-700 bg-rose-50 border border-rose-100 rounded-xl p-3">
              {formError}
            </div>
          )}

          <label className="block text-sm font-semibold mt-6">Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="mt-2 w-full border border-slate-200 rounded-xl px-3 py-3"
            placeholder="you@example.gov.in"
            disabled={loading}
            autoComplete="username"
          />
          {fieldErrors.email && <p className="text-xs text-rose-600 mt-1">{fieldErrors.email}</p>}

          <label className="block text-sm font-semibold mt-4">Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="mt-2 w-full border border-slate-200 rounded-xl px-3 py-3"
            placeholder="••••••••"
            disabled={loading}
            autoComplete="current-password"
          />
          {fieldErrors.password && <p className="text-xs text-rose-600 mt-1">{fieldErrors.password}</p>}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full mt-6 flex items-center justify-center gap-2 disabled:opacity-70"
          >
            {loading && <Loader2 size={16} className="animate-spin"/>}
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  </div>
}