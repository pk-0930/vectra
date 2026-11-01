import { useEffect, useState } from 'react'
import { useBusiness } from '../components/BusinessContext'
import { Button, PageHeader, StatusBadge } from '../design-system/components'
import { fetchInbox, readInboxItem, sendAnnouncement } from '../services/workspaceApi'
import type { Inbox } from '../services/workspaceApi'
import { gymRequest, type GymPurchase } from '../services/gymApi'
import MembershipPayment from '../components/MembershipPayment'

export default function InboxPage({ memberMode = false }: { memberMode?: boolean }) {
  const business = useBusiness()!
  const admin = !memberMode && business.staff_roles.some(role => role === 'owner' || role === 'admin')
  const canReviewPayments = admin && business.organization_type === 'gym'
  const [data, setData] = useState<Inbox | null>(null)
  const [purchases, setPurchases] = useState<GymPurchase[]>([])
  const [paymentsLoaded, setPaymentsLoaded] = useState(false)
  const [view, setView] = useState<'messages' | 'payments'>('messages')
  const [error, setError] = useState('')
  const [paymentError, setPaymentError] = useState('')
  const [busy, setBusy] = useState(false)
  const [audience, setAudience] = useState('all')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  const [sent, setSent] = useState('')
  useEffect(() => {
    let active = true
    fetchInbox().then(value => { if (active) setData(value) }).catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!canReviewPayments) return
    gymRequest<GymPurchase[]>('/gym/registrations').then(setPurchases).catch(err => setPaymentError(err instanceof Error ? err.message : 'Payment requests unavailable.')).finally(() => setPaymentsLoaded(true))
  }, [canReviewPayments])
  async function loadPayments() {
    setBusy(true); setPaymentError('')
    try { setPurchases(await gymRequest<GymPurchase[]>('/gym/registrations')); setPaymentsLoaded(true) }
    catch (err) { setPaymentError(err instanceof Error ? err.message : 'Payment requests unavailable.') }
    finally { setPaymentsLoaded(true); setBusy(false) }
  }
  const needsReview = purchases.filter(purchase => !['confirmed', 'refunded', 'superseded', 'cancelled'].includes(purchase.status))
  async function load(before?: number) {
    setBusy(true); setError('')
    try {
      const next = await fetchInbox(before)
      setData(previous => before && previous ? { ...next, items: [...previous.items, ...next.items] } : next)
    } catch (err) { setError(err instanceof Error ? err.message : 'Inbox unavailable.') }
    finally { setBusy(false) }
  }
  async function markRead(id: number) {
    setBusy(true); setError('')
    try {
      await readInboxItem(id)
      setData(previous => previous ? { ...previous, unread: Math.max(0, previous.unread - 1), items: previous.items.map(item => item.id === id ? { ...item, read_at: new Date().toISOString() } : item) } : previous)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to mark read.') }
    finally { setBusy(false) }
  }
  async function publish(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setSent('')
    try {
      const result = await sendAnnouncement({ request_id: requestId, audience, subject, message })
      setSent(`Announcement delivered to ${result.recipient_count} inboxes.`)
      setSubject(''); setMessage(''); setRequestId(crypto.randomUUID())
      setData(await fetchInbox())
    } catch (err) { setError(err instanceof Error ? err.message : 'Announcement failed. Retry with the same content.') }
    finally { setBusy(false) }
  }
  return <section className="page-content inbox-page">
    <PageHeader eyebrow={business.name} title="Inbox" description="Messages and items that need your attention." />
    {canReviewPayments && <nav className="inbox-views" aria-label="Inbox views"><button type="button" aria-current={view === 'messages' ? 'page' : undefined} onClick={() => setView('messages')}>Messages <span>{data?.unread ?? 0}</span></button><button type="button" aria-current={view === 'payments' ? 'page' : undefined} onClick={() => setView('payments')}>Payment verification <span>{needsReview.length}</span></button></nav>}
    {view === 'messages' && <>
    {error && <p role="alert">{error}</p>}
    <div className="workspace-shortcuts"><StatusBadge tone="info">{data?.unread ?? 0} unread</StatusBadge><Button variant="secondary" disabled={busy} onClick={() => void load()}>Refresh</Button></div>
    {!data && !error && <p role="status">Loading messages…</p>}
    {data?.items.length === 0 && <p>No messages yet.</p>}
    {data?.items.map(item => <article className="workspace-card" key={item.id}>
      <h2>{item.subject}</h2><time>{new Date(item.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST</time>
      <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.message}</p>
      {item.read_at ? <StatusBadge tone="neutral">Read</StatusBadge> : <Button disabled={busy} onClick={() => void markRead(item.id)}>Mark as read</Button>}
    </article>)}
    {data?.next_before && <Button disabled={busy} onClick={() => void load(data.next_before!)}>Older messages</Button>}
    {admin && <form className="workspace-card" onSubmit={event => void publish(event)}>
      <h2>Send a business announcement</h2><p>Recipients are active accounts in {business.name}. This sends an inbox message.</p>
      <label>Audience<select value={audience} disabled={busy} onChange={event => { setAudience(event.target.value); setRequestId(crypto.randomUUID()) }}><option value="all">Everyone in this business</option><option value="trainers">Trainers</option><option value="members">Gym members and registrants</option><option value="clients">Linked coaching clients</option></select></label>
      <label>Subject<input required maxLength={160} value={subject} disabled={busy} onChange={event => { setSubject(event.target.value); setRequestId(crypto.randomUUID()) }} /></label>
      <label>Message<textarea required maxLength={4000} value={message} disabled={busy} onChange={event => { setMessage(event.target.value); setRequestId(crypto.randomUUID()) }} /></label>
      <Button type="submit" disabled={busy || !subject.trim() || !message.trim()}>Send announcement</Button>{sent && <p role="status">{sent}</p>}
    </form>}
    </>}
    {view === 'payments' && canReviewPayments && <section className="inbox-payment-queue" aria-labelledby="payment-queue-title">
      <div className="inbox-queue-heading"><div><h2 id="payment-queue-title">Payment requests</h2><p>Review submitted payments. Check your actual bank or merchant receipt before confirming.</p></div><Button variant="secondary" disabled={busy} onClick={() => void loadPayments()}>Refresh list</Button></div>
      {paymentError && <p role="alert">{paymentError}</p>}
      {purchases.length === 0 && !paymentsLoaded && !paymentError && <p role="status">Loading payment requests…</p>}
      {purchases.length > 0 && needsReview.length === 0 && <p>No payment requests need review.</p>}
      {needsReview.map(purchase => <MembershipPayment key={purchase.id} purchase={purchase} admin onChange={updated => setPurchases(rows => rows.map(row => row.id === updated.id ? updated : row))} />)}
    </section>}
  </section>
}
