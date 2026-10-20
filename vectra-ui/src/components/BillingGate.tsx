import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { loadBilling } from '../services/billingApi'
import type { BillingSummary } from '../services/billingApi'
import BillingPage from '../pages/BillingPage'

export default function BillingGate({ organizationId, children }: { organizationId: number; children: ReactNode }) {
  const [billing, setBilling] = useState<BillingSummary | null>(null)
  const [error, setError] = useState('')
  const [showBilling, setShowBilling] = useState(false)
  const refresh = useCallback(async () => { setBilling(await loadBilling(organizationId)); setError('') }, [organizationId])
  useEffect(() => {
    let active = true
    const update = () => loadBilling(organizationId).then(value => { if (active) { setBilling(value); setError('') } }).catch(err => { if (active) setError(err.message) })
    void update()
    const timer = window.setInterval(() => { void update() }, 5000)
    window.addEventListener('focus', update)
    return () => { active = false; window.clearInterval(timer); window.removeEventListener('focus', update) }
  }, [organizationId])
  if (!billing) return <main id="workspace" tabIndex={-1} className="member-home"><p role={error ? 'alert' : 'status'}>{error || 'Checking business access…'}</p>{error && <button onClick={() => { void refresh().catch(err => setError(err.message)) }}>Retry</button>}</main>
  if (billing.access === 'pending' && !billing.owner) return <main id="workspace" tabIndex={-1} className="member-home"><h1>Business activation pending</h1><p>The owner needs to complete the software subscription payment.</p></main>
  return <>
    {error && <p role="alert" className="billing-banner">{error}</p>}
    {billing.owner && <nav className="workspace-shortcuts" aria-label="Software billing"><button onClick={() => setShowBilling(value => !value)}>{showBilling && billing.access !== 'pending' ? 'Back to workspace' : 'Software billing'}</button></nav>}
    {billing.access === 'read_only' && <p className="billing-banner">Read-only access. Existing records remain available. {billing.owner ? 'Renew in Software billing to make changes.' : 'Contact the owner to renew.'}</p>}
    {billing.access === 'grace' && <p className="billing-banner">Renewal needs attention. Grace ends {new Date(billing.grace_until!).toLocaleString('en-IN')}.</p>}
    {billing.owner && (showBilling || billing.access === 'pending') ? <BillingPage organizationId={organizationId} billing={billing} refresh={refresh} /> : children}
  </>
}
