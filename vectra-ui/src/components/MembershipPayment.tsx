import { useState } from 'react'
import { gymRequest, jsonRequest, rupees, type GymPurchase } from '../services/gymApi'
import { API_BASE_URL } from '../services/apiConfig'
import { Button, Card } from '../design-system/components'
import ProtectedImage from './ProtectedImage'

type Detail = { resolution_error?: string; pt_state: { reserved_until: string; resolution_reason: string | null; trainer_relationship_id: number } | null; pt: { starts_on: string; ends_before: string; remaining_sessions: number | null; revoked_at: string | null } | null; purchase: GymPurchase; events: { id: number; kind: string; details: Record<string, unknown>; created_at: string; actor_user_id: number; has_evidence: boolean }[]; membership: { starts_on: string; ends_before: string; status: string } | null; payment: { method: string; reference: string; amount_paise: number; received_on: string } | null }
export default function MembershipPayment({ purchase, admin = false, onChange, trainers = [] }: { purchase: GymPurchase; admin?: boolean; onChange?: (purchase: GymPurchase) => void; trainers?: { id: number; email: string }[] }) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [opened, setOpened] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [reference, setReference] = useState('')
  const [method, setMethod] = useState('upi')
  const [amount, setAmount] = useState('')
  const [received, setReceived] = useState('')
  const [start, setStart] = useState('')
  const [checked, setChecked] = useState(false)
  const [refundDone, setRefundDone] = useState(false)
  const [entitlement, setEntitlement] = useState('revoke')
  const [replacementTrainer, setReplacementTrainer] = useState('')
  const [consent, setConsent] = useState(false)
  const [termsConsent, setTermsConsent] = useState(false)
  const base = `/${admin ? 'gym' : 'member'}/purchases/${purchase.id}`
  const current = detail?.purchase ?? purchase
  const pending = ['pending', 'awaiting_verification', 'rejected'].includes(current.status)
  async function run(action?: string) {
    setBusy(true); setError('')
    try {
      if (action && amount && !/^\d+(\.\d{1,2})?$/.test(amount)) throw new Error('Enter an amount with at most two decimal places.')
      const result = await gymRequest<Detail>(action ? `${base}/${action}` : base, action ? jsonRequest('POST', { note, reference, method, amount_paise: amount ? Math.round(Number(amount) * 100) : null, received_on: received || null, starts_on: start || null, receipt_checked: checked, pt_terms_consent: termsConsent, external_refund_completed: refundDone, entitlement }) : {})
      setDetail(result); setOpened(true); if (result.resolution_error) setError(result.resolution_error); if (action) onChange?.(result.purchase)
    } catch (err) { setError(err instanceof Error ? err.message : 'Payment request failed.') }
    finally { setBusy(false) }
  }
  async function upload(file: File) {
    setBusy(true); setError('')
    try {
      const data = new FormData(); data.append('file', file)
      await gymRequest(`${base}/evidence`, { method: 'PUT', body: data })
      setDetail(await gymRequest<Detail>(base))
    } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed.') }
    finally { setBusy(false) }
  }
  return <Card><h3>{admin ? current.snapshot.member_name : 'Payment and membership'}</h3><p>{rupees(current.amount_paise)} · {current.status.replaceAll('_', ' ')}</p>
    <Button variant="secondary" disabled={busy} onClick={() => void run()}>View payment and membership</Button>
    {error && <p role="alert">{error}</p>}
    {opened && <div className="gym-payment-form">
      <p>UPI recipient recorded at purchase: {current.snapshot.payment.recipient_name} · {current.snapshot.payment.upi_id}. Check receipt with this recipient even if the gym has changed its QR.</p>
      {detail?.membership && <p><strong>Membership: {detail.membership.status}</strong> · starts {detail.membership.starts_on}; ends before {detail.membership.ends_before} (India calendar dates). <a href={`/join/${current.snapshot.public_id}`}>Renew membership</a></p>}
      {detail?.pt_state && <p>Trainer reservation ends {new Date(detail.pt_state.reserved_until).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST. Expired reservations require rechecking before payment. {detail.pt_state.resolution_reason && <strong>Resolution needed: {detail.pt_state.resolution_reason}</strong>}</p>}
      {detail?.pt && <p>PT: {detail.pt.starts_on} to before {detail.pt.ends_before}; {detail.pt.remaining_sessions === null ? 'duration package' : `${detail.pt.remaining_sessions} session credit`}{detail.pt.revoked_at ? ' · revoked' : ''}.</p>}
      {admin && pending && current.snapshot.plans.some(p => p.kind === 'pt') && <><label>Replacement trainer<select value={replacementTrainer} onChange={e => setReplacementTrainer(e.target.value)}><option value="">Select trainer</option>{trainers.map(t => <option key={t.id} value={t.id}>{t.email}</option>)}</select></label><label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />Member consent to reassignment is recorded in the note below</label><Button disabled={busy || !consent || !replacementTrainer || !note} onClick={async () => { setBusy(true); setError(''); try { await gymRequest(`${base}/reassign-pt`, jsonRequest('POST', { trainer_relationship_id: Number(replacementTrainer), member_consent: consent, note })); setDetail(await gymRequest<Detail>(base)) } catch (err) { setError(err instanceof Error ? err.message : 'Reassignment failed.') } finally { setBusy(false) } }}>Resolve with replacement trainer</Button></>}
      {detail?.payment && <p>Confirmed collection: {rupees(detail.payment.amount_paise)} · {detail.payment.method} · {detail.payment.reference} · received {detail.payment.received_on}</p>}
      <p>Screenshots and submitted references are claims. The gym must check actual bank/merchant receipt or record cash received. Vectra has no bank notification access.</p>
      <label>Reference / cash receipt number<input value={reference} maxLength={120} onChange={e => setReference(e.target.value)} /></label>
      <label>{admin ? 'Verification / exception / correction note' : 'Payment details or cancellation reason'}<textarea value={note} maxLength={2000} onChange={e => setNote(e.target.value)} /></label>
      {!admin && pending && <><label>Optional screenshot (PNG/JPEG, up to 2 MB)<input type="file" accept="image/png,image/jpeg" disabled={busy} onChange={e => { if (e.target.files?.[0]) void upload(e.target.files[0]) }} /></label><Button disabled={busy} onClick={() => void run('submit')}>Submit for verification</Button><Button variant="secondary" disabled={busy} onClick={() => void run('cancel')}>Cancel unpaid purchase</Button></>}
      {admin && <>
        <label>Method<select value={method} onChange={e => setMethod(e.target.value)}><option value="upi">UPI</option><option value="cash">Cash</option></select></label>
        <label>Actual amount received / externally refunded (₹)<input type="number" min="0.01" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} /></label>
        {pending && <><label>Actual receipt date<input type="date" value={received} onChange={e => setReceived(e.target.value)} /></label><label>Optional membership start date<input type="date" value={start} onChange={e => setStart(e.target.value)} /></label><p>Defaults to today. Renewals extend existing paid coverage. Calendar months clamp to month-end; dates cannot be backdated.</p><label><input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} />I checked actual merchant/bank receipt or received this cash and recorded its receipt number.</label>
        {current.snapshot.plans.some(p => p.kind === 'pt') && <p role="status">PT bundle: retain any receipt for admin resolution. Paid gym coverage and trainer capacity are rechecked before activation. Do not ask the member to pay twice.</p>}
        {current.snapshot.plans.some(p => p.kind === 'pt') && !current.snapshot.pt_service_terms && <label><input type="checkbox" checked={termsConsent} onChange={e => setTermsConsent(e.target.checked)} />Member accepted current PT terms: 60-minute sessions; duration packages one per day; single credit expires within 30 days; only completion consumes credit; reassignment needs consent.</label>}
        <Button disabled={busy || !checked || current.status === 'rejected'} onClick={() => void run('confirm')}>Confirm payment and activate membership</Button><Button variant="secondary" disabled={busy} onClick={() => void run('reject')}>Reject with reason</Button><Button variant="secondary" disabled={busy} onClick={() => void run('cancel')}>Cancel unpaid purchase</Button></>}
        {(current.status === 'confirmed' || pending) && <><p>Refunds must be performed outside Vectra. This records a full refund only; no money is transferred. Existing renewal periods keep their dates.</p><label><input type="checkbox" checked={refundDone} onChange={e => setRefundDone(e.target.checked)} />External full refund completed</label><label>Membership consequence<select value={entitlement} onChange={e => setEntitlement(e.target.value)}><option value="revoke">Revoke this purchase’s gym/PT entitlements</option><option value="retain">Retain existing entitlements</option></select></label><Button disabled={busy || !refundDone} onClick={() => void run('refund')}>Record external refund</Button></>}
        <Button variant="secondary" disabled={busy} onClick={() => void run('correct')}>Append correction note</Button>
      </>}
      <h4>Payment history</h4>{detail?.events.map(event => <div key={event.id}><p>{event.kind} · {new Date(event.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} · recorded by user {event.actor_user_id}</p><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(event.details, null, 2)}</pre>{admin && event.has_evidence && <ProtectedImage src={`${API_BASE_URL}${base}/evidence/${event.id}`} alt="Member-submitted evidence, not verified receipt" />}</div>)}
    </div>}
  </Card>
}
