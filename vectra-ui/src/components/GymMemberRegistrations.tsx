import MembershipPayment from './MembershipPayment'
import { useEffect, useState } from 'react'
import { gymRequest, type GymPurchase } from '../services/gymApi'
import { PurchaseCard } from '../pages/GymJoinPage'
import { Button } from '../design-system/components'

export default function GymMemberRegistrations() {
  const [items, setItems] = useState<GymPurchase[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    gymRequest<GymPurchase[]>('/member/gym-registrations').then(rows => { if (!cancelled) setItems(rows) }).catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Unable to load registrations.') })
    return () => { cancelled = true }
  }, [])
  return <section aria-label="Gym registrations">{error && <p role="alert">{error}</p>}{items.map(p => <div key={p.id}><MembershipPayment purchase={p} onChange={updated => setItems(rows => rows.map(row => row.id === updated.id ? updated : row))} /><PurchaseCard purchase={p} onRefresh={() => { window.location.href = `/join/${p.snapshot.public_id}` }} />{p.status === 'pending' && <Button variant="secondary" onClick={() => { window.location.href = `/join/${p.snapshot.public_id}` }}>Open gym registration</Button>}</div>)}</section>
}
