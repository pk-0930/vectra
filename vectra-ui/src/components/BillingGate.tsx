import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { loadBilling } from '../services/billingApi'
import type { BillingSummary } from '../services/billingApi'

export default function BillingGate({ organizationId, children }: { organizationId: number; children: (billing: BillingSummary, refresh: () => Promise<void>) => ReactNode }) {
  const [billing, setBilling] = useState<BillingSummary | null>(null)
  const [error, setError] = useState('')
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
    {children(billing, refresh)}
  </>
}
