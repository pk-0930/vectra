import { useState } from 'react'
import { API_BASE_URL } from '../services/apiConfig'
import { loginUser } from '../services/authApi'
import { buildAuthHeaders, getStoredAccessToken, setStoredAccessToken } from '../services/session'

async function emailRequest(kind: 'verify' | 'recover', email: string) {
  const response = await fetch(`${API_BASE_URL}/auth/email/${kind}/request`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }),
  })
  const result = await response.json()
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Unable to send. Try again later.')
  return result.message as string
}

export default function EmailActionPage({ action, token, onBack }: { action: string; token: string; onBack: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newAccount, setNewAccount] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [signedIn, setSignedIn] = useState(Boolean(getStoredAccessToken()))
  const invitation = action === 'invite'
  const request = action === 'request-recovery'
  const valid = ['verify', 'recover', 'invite', 'request-recovery'].includes(action)
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true); setError(''); setMessage('')
    try {
      if (request) {
        setMessage(await emailRequest('recover', email)); setDone(true)
      } else {
        if (invitation && !signedIn && !newAccount) {
          await loginUser({ email, password }); setSignedIn(true)
        }
        const response = await fetch(`${API_BASE_URL}/auth/email/${action}/confirm`, {
          method: 'POST', headers: invitation && !newAccount ? buildAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, ...(invitation ? { email } : {}), ...((action === 'recover' || (invitation && newAccount)) ? { password } : {}) }),
        })
        const result = await response.json()
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Unable to complete this request.')
        if (action === 'recover') setStoredAccessToken('')
        setPassword(''); setMessage(result.message); setDone(true)
      }
    } catch (err) { setError(err instanceof Error ? err.message : 'Request failed.') }
    finally { setBusy(false) }
  }
  return <main className="identity-page"><section className="workspace-card identity-card">
    <p className="identity-brand">VECTRA</p>
    <h1>{request ? 'Forgot your password?' : invitation ? 'Join your business' : action === 'recover' ? 'Choose a new password' : 'Verify your email'}</h1>
    <p>{request ? 'We’ll email a recovery link if your account is eligible.' : invitation ? 'Use the email address that received this invitation. Existing accounts must sign in; new recipients can create an account here.' : action === 'recover' ? 'Your other sessions will be signed out when you save your password.' : 'Confirm that this email address belongs to you.'}</p>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {!valid ? <p role="alert">This link is not supported.</p> : !done && <form onSubmit={submit}>
      {(request || invitation) && <label>Email address<input type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} /></label>}
      {invitation && !signedIn && <label className="identity-choice"><input type="checkbox" checked={newAccount} onChange={e => { setNewAccount(e.target.checked); setPassword('') }} />I’m creating a new account</label>}
      {(action === 'recover' || (invitation && !signedIn)) && <label>{newAccount || action === 'recover' ? 'New password (at least 12 characters)' : 'Password'}<input type="password" required minLength={newAccount || action === 'recover' ? 12 : undefined} maxLength={256} autoComplete={newAccount || action === 'recover' ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} /></label>}
      <button disabled={busy}>{busy ? 'Please wait…' : request ? 'Send recovery link' : invitation ? 'Accept invitation' : action === 'recover' ? 'Save password' : 'Verify email'}</button>
    </form>}
    {invitation && signedIn && !done && <button disabled={busy} onClick={() => { setStoredAccessToken(''); setSignedIn(false); setNewAccount(false) }}>Sign out to use a different account</button>}
    <button className="identity-secondary" disabled={busy} onClick={onBack}>{done ? 'Continue to Vectra' : 'Back to sign in'}</button>
  </section></main>
}

export function VerifyEmailPage({ email, onLogout, embedded = false }: { email: string; onLogout: () => void; embedded?: boolean }) {
  const Container = embedded ? 'section' : 'main'
  const Heading = embedded ? 'h3' : 'h1'
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  async function resend() {
    setBusy(true)
    try { setMessage(await emailRequest('verify', email)) }
    catch (err) { setMessage(err instanceof Error ? err.message : 'Unable to send email.') }
    finally { setBusy(false) }
  }
  return <Container className="identity-page"><section className="workspace-card identity-card"><p className="identity-brand">VECTRA</p><Heading>Check your inbox</Heading><p>We sent a verification link to {email}. Verify your address to open your workspace.</p><p role="status">{message}</p><button disabled={busy} onClick={() => void resend()}>{busy ? 'Sending…' : 'Resend verification email'}</button><button onClick={() => window.location.reload()}>I’ve verified my email</button><button className="identity-secondary" onClick={onLogout}>Sign out</button></section></Container>
}
