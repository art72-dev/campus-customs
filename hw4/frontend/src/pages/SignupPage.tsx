import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../AuthContext'

export default function SignupPage() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '', confirm_password: '' })
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }))

  const mismatch = form.confirm_password.length > 0 && form.password !== form.confirm_password

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (form.password !== form.confirm_password) {
      setError("Passwords don't match")
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      setUser(await api.signup(form))
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Join the squad</h1>
        <p className="muted small">Create an account to save your favs and chat with our bot.</p>
        <div className="row">
          <label>
            First name
            <input value={form.first_name} onChange={update('first_name')} required autoComplete="given-name" />
          </label>
          <label>
            Last name
            <input value={form.last_name} onChange={update('last_name')} required autoComplete="family-name" />
          </label>
        </div>
        <label>
          Email
          <input type="email" value={form.email} onChange={update('email')} required autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={update('password')}
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
          />
          <span className="hint">At least 8 characters</span>
        </label>
        <label>
          Confirm password
          <input
            type="password"
            value={form.confirm_password}
            onChange={update('confirm_password')}
            required
            autoComplete="new-password"
            aria-invalid={mismatch}
          />
          {mismatch && <span className="hint error">Passwords don't match</span>}
        </label>
        {error && <div className="error-box">{error}</div>}
        <button type="submit" className="btn btn-primary btn-block" disabled={submitting || mismatch}>
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
        <p className="muted small">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  )
}
