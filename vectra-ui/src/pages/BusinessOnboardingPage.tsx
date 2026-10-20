import { useState } from 'react'
import { billingRequest } from '../services/billingApi'
import { setStoredAccessToken } from '../services/session'
import type { LoginResponse } from '../types/auth'

export default function BusinessOnboardingPage({ register = false, onBack }: { register?: boolean; onBack: () => void }) {
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
      if (register) {
        const result = await billingRequest<LoginResponse>('/auth/register-business', 'POST', { ...data, email, password })
        setStoredAccessToken(result.access_token)
      } else {
        const result = await billingRequest<{ organization_id: number }>('/organizations', 'POST', data)
        window.sessionStorage.setItem('vectra.onboardingBusiness', String(result.organization_id))
      }
      window.location.reload()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save your business.'); setBusy(false) }
  }
  return <main className="identity-page"><section className="workspace-card identity-card"><p className="identity-brand">VECTRA</p><h1>{register ? 'Start your business workspace' : 'Add a business'}</h1>
    <p>Choose the business you run. Each business has its own workspace and Vectra software subscription.</p>
    <form onSubmit={submit}><label>Business name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Business type<select value={kind} onChange={e => setKind(e.target.value)}><option value="gym">Gym</option><option value="coaching">Independent online coaching</option></select></label>
      {register && <><label>Email address<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label><label>Password (at least 12 characters)<input type="password" autoComplete="new-password" minLength={12} maxLength={256} required value={password} onChange={e => setPassword(e.target.value)} /></label></>}
      <p>Your setup is saved before checkout. {register ? 'Verify your email, then choose your software plan.' : 'Choose your software plan next.'} No paid access starts until payment is verified.</p>
      {error && <p role="alert">{error}</p>}<button disabled={busy}>{busy ? 'Saving…' : register ? 'Create account and save business' : 'Save business'}</button>
    </form><button className="identity-secondary" disabled={busy} onClick={onBack}>{register ? 'Already have an account? Sign in' : 'Back'}</button>
  </section></main>
}
