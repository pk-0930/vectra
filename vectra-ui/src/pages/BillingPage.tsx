import { Button, Dialog, PageHeader, StatusBadge } from '../design-system/components'
import { useState } from 'react'
import { billingRequest, openSoftwareCheckout } from '../services/billingApi'
import type { BillingSummary, CheckoutResult } from '../services/billingApi'

const money = (amount: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(amount / 100)
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-IN') : 'No paid period yet'

export default function BillingPage({ organizationId, billing, refresh }: { organizationId: number; billing: BillingSummary; refresh: () => Promise<void> }) {
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [acceptedTerms, setAcceptedTerms] = useState('')
  const consentKey = JSON.stringify([billing.terms_version, billing.terms, billing.plans])
  const accepted = acceptedTerms === consentKey
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const subscription = billing.subscription
  const terminal = !subscription || ['cancelled', 'completed', 'expired', 'creation_failed'].includes(subscription.status)
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(''); setMessage('')
    try { await action(); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'Billing request failed.') }
    finally { setBusy(false) }
  }
  async function paid(result: CheckoutResult) {
    await run(async () => {
      await billingRequest(`/organizations/${organizationId}/billing/verify`, 'POST', result)
      setMessage('Checkout received. We’re verifying the paid invoice. Authorization alone does not activate access.')
    })
  }
  return <main id="workspace" tabIndex={-1} className="member-home billing-page"><PageHeader eyebrow="Business / subscription" title={`Billing for ${billing.business_name}`} description="Your Vectra software subscription. Gym membership and PT collections are separate." />
    {billing.mode === 'test' && <p className="billing-banner">Test mode — test payments do not grant live billing access.</p>}
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <section className="workspace-card"><div className="section-heading"><h2>Workspace access</h2><StatusBadge tone={billing.access === 'active' || billing.access === 'legacy' ? 'success' : 'warning'}>{{ pending: 'Awaiting payment', active: 'Active', grace: 'Renewal grace period', read_only: 'Read-only', legacy: 'Legacy access' }[billing.access]}</StatusBadge></div><p>Paid through: {date(billing.paid_through)}</p>
      {billing.access === 'legacy' && <p>Existing access is preserved. {billing.legacy_until ? `Transition ends ${date(billing.legacy_until)}.` : 'No transition deadline has been scheduled.'}</p>}
      {billing.access === 'grace' && <p>Renewal needs attention. You can continue making changes until {date(billing.grace_until)}.</p>}
      {billing.access === 'read_only' && <p>Existing records are readable. Renew to resume making changes.</p>}
      {billing.access === 'pending' && <p>Your business setup is saved. A verified subscription payment is required to open the workspace.</p>}
      {subscription && <><p>Subscription: {subscription.status.replaceAll('_', ' ')} · {subscription.plan.name}</p><p>{money(subscription.plan.amount_paise)} every {subscription.plan.interval} {subscription.plan.period === 'monthly' ? 'month(s)' : 'year(s)'}</p>
        {subscription.error_code && <p role="alert">Billing needs attention ({subscription.error_code}). Refresh verification or contact support. Do not make a second payment while the result is uncertain.</p>}
        {subscription.cancel_requested && <p>{subscription.cancel_confirmed ? 'Cancellation confirmed.' : 'Cancellation is awaiting provider confirmation.'} Paid coverage remains until its end date.</p>}
      </>}
      <button disabled={busy || !subscription} onClick={() => void run(async () => { await billingRequest(`/organizations/${organizationId}/billing/refresh`, 'POST'); setMessage('Verification queued. This page updates automatically.') })}>Refresh payment verification</button>
    </section>
    {!billing.checkout_available && <section className="workspace-card"><h2>Checkout is not available yet</h2><p>Your business setup is saved. Software plans and payment configuration must be enabled before you can subscribe.</p></section>}
    {terminal && <section className="workspace-card"><h2>{subscription ? 'Reactivate your subscription' : 'Choose a software plan'}</h2><div className="billing-plans">{billing.plans?.map(plan => <article key={plan.code}><h3>{plan.name}</h3><p className="billing-price">{money(plan.amount_paise)}</p><p>Every {plan.interval} {plan.period === 'monthly' ? 'month(s)' : 'year(s)'} · {plan.total_count} billing cycles</p><button disabled={busy || !accepted || !billing.checkout_available} onClick={() => void run(async () => { await billingRequest(`/organizations/${organizationId}/billing/checkout`, 'POST', { plan_code: plan.code, accept_terms: accepted, terms_version: billing.terms_version }); setMessage('Preparing secure checkout. Your progress is saved; this page will update.') })}>Choose {plan.name}</button></article>)}</div>
      <p>{billing.terms}</p><label><input type="checkbox" checked={accepted} onChange={e => setAcceptedTerms(e.target.checked ? consentKey : '')} /> I accept these recurring billing terms.</label>
    </section>}
    {!terminal && subscription && <section className="workspace-card"><h2>Manage subscription</h2>
      {['queued', 'creating', 'creation_unknown'].includes(subscription.status) && <p>Preparing or reconciling your checkout. You can return later; we’ll use the same subscription attempt.</p>}
      {subscription.provider_id && !subscription.cancel_requested && ['created','authenticated','pending','halted','paused'].includes(subscription.status) && <button disabled={busy || !billing.checkout_available} onClick={() => void run(async () => { await openSoftwareCheckout(subscription, billing.business_name, result => { void paid(result) }, () => setMessage('Checkout closed. Your setup is saved; you can resume here.'), () => setError('Payment did not complete. Your setup is saved.')) })}>Open secure Razorpay checkout</button>}
      <Button variant="danger" disabled={busy || subscription.cancel_requested} onClick={() => setConfirmCancel(true)}>Cancel future renewals</Button>
      <p>Refunds are reviewed by support and processed through Razorpay. Cancelling does not automatically issue a refund.</p>
    </section>}
    <section className="workspace-card"><h2>Verified payment history</h2>{!billing.payments?.length && <p>No verified software payments yet.</p>}{billing.payments?.map(payment => <article key={payment.payment_id}><strong>{money(payment.amount_paise)}</strong><p>{date(payment.period_start)} – {date(payment.period_end)}</p><p>Invoice: {payment.invoice_id}</p>{payment.refunded_paise > 0 && <p>Refunded: {money(payment.refunded_paise)}</p>}</article>)}</section>
    <Dialog open={confirmCancel} title="Stop future renewals?" onClose={() => setConfirmCancel(false)}><p>Your existing paid coverage remains until its end date. Cancellation does not automatically issue a refund.</p><div className="header-actions"><Button variant="secondary" onClick={() => setConfirmCancel(false)}>Keep subscription</Button><Button variant="danger" disabled={busy} onClick={() => { setConfirmCancel(false); void run(async () => { await billingRequest(`/organizations/${organizationId}/billing/cancel`, 'POST'); setMessage('Cancellation queued for provider confirmation.') }) }}>Confirm cancellation</Button></div></Dialog>
  </main>
}
