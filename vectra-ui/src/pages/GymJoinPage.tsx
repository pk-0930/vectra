import { useEffect, useState } from 'react'
import type { AuthUser, LoginResponse } from '../types/auth'
import { loginUser } from '../services/authApi'
import { setStoredAccessToken } from '../services/session'
import { GymApiError, gymRequest, jsonRequest, publicGymAsset, rupees, type GymPurchase, type PublicGym } from '../services/gymApi'
import { Button, Card, EmptyState, Skeleton, StatusBadge } from '../design-system/components'
import { VerifyEmailPage } from './EmailActionPage'

export function PurchaseCard({ purchase, onRefresh }: { purchase: GymPurchase; onRefresh?: () => void }) {
  const p = purchase
  return <Card><StatusBadge tone={p.status === 'pending' ? 'warning' : 'neutral'}>{p.status === 'pending' ? 'Pending registration · no paid access' : p.status.replaceAll('_', ' ')}</StatusBadge><h2>{p.snapshot.gym_name}</h2>
    <p>{p.snapshot.member_name} · {new Date(p.created_at).toLocaleDateString()}</p>
    {p.snapshot.plans.map(plan => <div key={plan.id} className="gym-purchase-plan"><strong>{plan.name} · {rupees(plan.amount_paise)}</strong><p>{plan.trainer_name}{plan.trainer_name && ' · '}{plan.sessions ? 'One session' : `${plan.duration_months} months`}</p><p className="gym-preserve-lines">{plan.terms}</p></div>)}
    <p className="gym-total">Total: {rupees(p.amount_paise)}</p>{!['confirmed', 'refunded'].includes(p.status) && <p>{p.snapshot.terms}</p>}<p><a href="/">Open your member workspace to submit payment, view membership dates, or renew.</a></p>
    <details><summary>Payment instructions saved with this registration</summary><p>Recipient: <strong>{p.snapshot.payment.recipient_name}</strong><br />UPI: {p.snapshot.payment.upi_id}</p>{p.snapshot.payment.qr_asset_id && <img className="gym-payment-qr" src={publicGymAsset(p.snapshot.payment.qr_asset_id)} alt="Gym payment QR saved with this registration" />}<p>Contact the gym before paying. Registration alone does not confirm payment or activate your plan.</p></details>
    {p.needs_review && p.status === 'pending' && <div className="gym-notice"><p>The gym’s setup has changed. Your saved prices and payment instructions above have not changed. Review current details before making a payment.</p>{onRefresh && <Button variant="secondary" onClick={onRefresh}>Review current catalogue</Button>}</div>}
  </Card>
}

export default function GymJoinPage({ publicId, user, onLogout }: { publicId: string; user: AuthUser | null; onLogout: () => void }) {
  const [gym, setGym] = useState<PublicGym | null>(null)
  const [history, setHistory] = useState<GymPurchase[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [gymPlan, setGymPlan] = useState('')
  const [ptOptions, setPtOptions] = useState<{ plans: { id: string; eligible: boolean; reason: string | null }[]; coverage: { starts_on: string; ends_before: string }[] } | null>(null)
  const [ptPlan, setPtPlan] = useState('')
  const [memberName, setMemberName] = useState('')
  const [mobile, setMobile] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [requestId, setRequestId] = useState(crypto.randomUUID())
  const [replaces, setReplaces] = useState<string | null>(null)
  const [newAccount, setNewAccount] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [stale, setStale] = useState(false)
  async function load() {
    setLoading(true); setError('')
    try {
      const data = await gymRequest<PublicGym>(`/public/gyms/${publicId}`, {}, false)
      setGym(data); setAccepted(false); setStale(false)
      if (user) setHistory(await gymRequest<GymPurchase[]>(`/public/gyms/${publicId}/purchases`))
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to open registration.') }
    finally { setLoading(false) }
  }
  useEffect(() => {
    // The value is an allowlisted local path, never an arbitrary redirect.
    sessionStorage.setItem('vectra.pendingGymJoin', `/join/${publicId}`)
    let cancelled = false
    Promise.all([gymRequest<PublicGym>(`/public/gyms/${publicId}`, {}, false), user ? gymRequest<GymPurchase[]>(`/public/gyms/${publicId}/purchases`) : Promise.resolve([])])
      .then(([data, purchases]) => { if (!cancelled) { setGym(data); setHistory(purchases) } })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Registration unavailable.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [publicId, user])
  useEffect(() => {
    let active = true
    if (user) gymRequest<typeof ptOptions>(`/public/gyms/${publicId}/pt-options`).then(result => { if (active) setPtOptions(result) }).catch(() => { if (active) setPtOptions(null) })
    return () => { active = false }
  }, [publicId, user])
  async function authenticate(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      if (newAccount) {
        const result = await gymRequest<LoginResponse>('/auth/register-member', jsonRequest('POST', { email, password, public_id: publicId }), false)
        setStoredAccessToken(result.access_token)
      } else await loginUser({ email, password })
      window.location.reload()
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to sign in.'); setBusy(false) }
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!gym) return
    setBusy(true); setError('')
    try {
      const purchase = await gymRequest<GymPurchase>(`/public/gyms/${publicId}/join`, jsonRequest('POST', { request_id: requestId, revision: gym.revision, plan_ids: [...(gymPlan ? [gymPlan] : []), ...(ptPlan ? [ptPlan] : [])], member_name: memberName, mobile, accept_terms: accepted, replaces_id: replaces }))
      setHistory(current => [purchase, ...current.filter(p => p.id !== purchase.id).map(p => p.id === replaces ? { ...p, status: 'superseded' as const } : p)])
      setSubmitted(true); setAccepted(false); setReplaces(null)
    } catch (err) {
      if (err instanceof GymApiError && err.status === 409) { setStale(true); setAccepted(false) }
      setError(err instanceof Error ? err.message : 'Unable to submit registration.')
    } finally { setBusy(false) }
  }
  const selected = gym?.available ? gym.plans.filter(p => p.id === gymPlan || p.id === ptPlan) : []
  const total = selected.reduce((sum, p) => sum + p.amount_paise, 0)
  function changed() { setAccepted(false); setRequestId(crypto.randomUUID()) }
  return <main className="gym-join"><header className="gym-public-bar"><a href="/">VECTRA</a><span>Gym registration</span>{user && <Button variant="tertiary" onClick={onLogout}>Sign out</Button>}</header>
    {error && <div role="alert" className="gym-notice">{error}<Button variant="secondary" disabled={busy || loading} onClick={() => void load()}>Refresh catalogue</Button></div>}
    {loading ? <Skeleton label="Opening gym registration…" /> : <>
      {gym?.available ? <>
        <section className="gym-hero">{gym.logo_id && <img className="gym-logo" src={publicGymAsset(gym.logo_id)} alt={`${gym.display_name} logo`} />}<p className="eyebrow">Your next step starts here</p><h1>{gym.display_name}</h1><p className="gym-preserve-lines">{gym.description}</p><p>{gym.address}</p><p>{gym.contact_phone}</p><StatusBadge>No app download required</StatusBadge></section>
        {submitted && <Card><h2>Your registration is saved</h2><p>The gym can see your pending registration. No payment has been verified and no paid membership or PT access has been activated.</p><Button onClick={() => { sessionStorage.removeItem('vectra.pendingGymJoin'); window.location.href = '/' }}>Open my workspace</Button></Card>}
        {!submitted && <div className="gym-join-layout"><section><h2>Choose your gym plan</h2><label><input type="radio" name="gym-plan" checked={!gymPlan} onChange={() => { setGymPlan(''); changed() }} />PT only — use existing paid membership</label><div className="gym-catalogue">{gym.plans.filter(p => p.kind === 'gym').map(plan => <label className={`gym-plan-choice ${gymPlan === plan.id ? 'selected' : ''}`} key={plan.id}><input type="radio" name="gym-plan" value={plan.id} checked={gymPlan === plan.id} onChange={() => { setGymPlan(plan.id); changed() }} /><span><strong>{plan.name}</strong><span className="gym-plan-price">{rupees(plan.amount_paise)}</span><span>{plan.duration_months} months · manual renewal</span><span className="gym-preserve-lines">{plan.terms}</span></span></label>)}</div>
          {gym.plans.some(p => p.kind === 'pt') && <><h2>Personal training <span className="gym-muted">Optional</span></h2><label className="gym-checkbox"><input type="radio" name="pt-plan" checked={!ptPlan} onChange={() => { setPtPlan(''); changed() }} />No PT plan</label><div className="gym-catalogue">{gym.plans.filter(p => p.kind === 'pt').map(plan => <label className={`gym-plan-choice ${ptPlan === plan.id ? 'selected' : ''}`} key={plan.id}><input type="radio" name="pt-plan" disabled={!ptOptions?.plans.find(p => p.id === plan.id)?.eligible} checked={ptPlan === plan.id} onChange={() => { setPtPlan(plan.id); changed() }} /><span><strong>{plan.name}</strong><span>{plan.trainer_name}</span><span className="gym-plan-price">{rupees(plan.amount_paise)}</span><span>{plan.sessions ? 'One session (expires within 30 days or at membership expiry)' : `${plan.duration_months} months`}</span><span>{ptOptions?.plans.find(p => p.id === plan.id)?.reason ?? (!ptOptions ? 'Paid membership is required. Sign in and activate gym coverage first.' : '')}</span><span className="gym-preserve-lines">{plan.terms}</span></span></label>)}</div><p>PT requires existing continuous paid gym coverage; a pending gym purchase is not coverage. Renew and verify membership first if a package is disabled. Saving a PT purchase reserves one trainer slot for 24 hours. Do not pay after reservation expiry without checking with reception.</p></>}
          <p>PT terms: 60-minute sessions; duration packages allow one session per day; only completion consumes credit, cancellation does not. Single-session credit expires within 30 days. Trainer reassignment needs member consent.</p>{ptOptions?.coverage.map((period, index) => <p key={index}>Paid gym coverage: {period.starts_on} to before {period.ends_before}. Select and verify a gym renewal above if more coverage is needed.</p>)}
        </section><section className="gym-join-summary"><Card><h2>Review your registration</h2><p className="gym-total">{rupees(total)}</p><p>Recipient: <strong>{gym.payment.recipient_name}</strong><br />UPI: {gym.payment.upi_id}</p>{gym.payment.qr_asset_id && <img className="gym-payment-qr" src={publicGymAsset(gym.payment.qr_asset_id)} alt="Gym payment QR; this is not the registration QR" />}<p>Confirm these details with reception before paying. This step saves a pending registration only.</p>
          {!user ? <form onSubmit={authenticate}><h3>{newAccount ? 'Create your personal account' : 'Sign in to continue'}</h3><p>One account works across gyms. Already registered? Sign in with your existing email.</p><label>Email<input type="email" required autoComplete="email" maxLength={254} value={email} onChange={e => setEmail(e.target.value)} /></label><label>{newAccount ? 'Password (at least 12 characters)' : 'Password'}<input type="password" required minLength={newAccount ? 12 : undefined} maxLength={256} autoComplete={newAccount ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} /></label><Button type="submit" disabled={busy}>{busy ? 'Please wait…' : newAccount ? 'Create account' : 'Sign in'}</Button><Button variant="tertiary" disabled={busy} onClick={() => setNewAccount(!newAccount)}>{newAccount ? 'I already have an account' : 'Create a new account'}</Button><a href="/#action=request-recovery">Forgot password?</a></form> : user.verification_required ? <VerifyEmailPage embedded email={user.email} onLogout={onLogout} /> : <form onSubmit={submit}>
            <p>Signed in as {user.email}</p><label>Full name<input required maxLength={120} autoComplete="name" value={memberName} onChange={e => { setMemberName(e.target.value); changed() }} /></label><label>Contact phone<input type="tel" required minLength={7} maxLength={25} autoComplete="tel" value={mobile} onChange={e => { setMobile(e.target.value); changed() }} /></label>
            {replaces && <p>This will supersede your previous pending registration with a new record. Its original details remain in your history.</p>}
            <label className="gym-checkbox"><input type="checkbox" required checked={accepted} onChange={e => setAccepted(e.target.checked)} />I have reviewed the selected plans, terms, total and payment destination. I understand registration does not activate paid membership or PT.</label><Button type="submit" disabled={busy || stale || (!gymPlan && !ptPlan) || (Boolean(ptPlan) && !ptOptions?.plans.find(p => p.id === ptPlan)?.eligible) || !accepted}>{busy ? 'Saving…' : replaces ? 'Confirm replacement registration' : 'Save pending registration'}</Button>
          </form>}
        </Card></section></div>}
      </> : <EmptyState title="Registration is currently unavailable">{gym?.reason === 'not_found' ? 'This gym registration link could not be found. Check the link with reception.' : 'The gym is not accepting registrations at this link right now. Contact reception or try again later.'}</EmptyState>}
      {history.length > 0 && <section aria-label="Your registration history"><h2>Your registrations</h2>{history.map(p => <PurchaseCard key={p.id} purchase={p} onRefresh={gym?.available ? () => { setSubmitted(false); setReplaces(p.id); setMemberName(p.snapshot.member_name); setMobile(p.snapshot.mobile); setGymPlan(''); setPtPlan(''); changed(); void load(); window.scrollTo({ top: 0, behavior: 'smooth' }) } : undefined} />)}</section>}
    </>}
  </main>
}
