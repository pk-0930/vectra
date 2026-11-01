import { useState } from 'react'
import { billingRequest } from '../services/billingApi'
import { setStoredAccessToken } from '../services/session'
import type { LoginResponse } from '../types/auth'

export default function BusinessOnboardingPage({ onBack }: { onBack: () => void }) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState('gym')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [requestId] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const data = { request_id: requestId, business_name: name, business_type: kind }
      const result = await billingRequest<LoginResponse>('/auth/register-business', 'POST', { ...data, email, password })
      setStoredAccessToken(result.access_token)
      window.location.reload()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save your workspace.'); setBusy(false) }
  }
  return <main className="identity-page"><section className="workspace-card identity-card"><p className="identity-brand">VECTRA</p><h1>Create your workspace</h1>
    <p>Choose Gym or Independent Online Coach. This name will appear throughout your workspace.</p>
    <form onSubmit={submit}><label>{kind === 'gym' ? 'Gym name' : 'Coaching name'}<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Business type<select value={kind} onChange={e => setKind(e.target.value)}><option value="gym">Gym</option><option value="coaching">Independent Online Coach</option></select></label>
      <label>Email address<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label><label>Password (at least 12 characters)<input type="password" autoComplete="new-password" minLength={12} maxLength={256} required value={password} onChange={e => setPassword(e.target.value)} /></label>
      <p>Your workspace is saved before checkout. Verify your email, then choose a software plan. No paid access starts until payment is verified.</p>
      {error && <p role="alert">{error}</p>}<button disabled={busy}>{busy ? 'Saving…' : 'Create account and save workspace'}</button>
    </form><button className="identity-secondary" disabled={busy} onClick={onBack}>Already have an account? Sign in</button>
  </section></main>
}
