import MembershipPayment from '../components/MembershipPayment'
import { useEffect, useState } from 'react'
import { Button, Card, Dialog, EmptyState, PageHeader, Skeleton } from '../design-system/components'
import ProtectedImage from '../components/ProtectedImage'
import { downloadRegistration, gymRequest, jsonRequest, privateGymAsset, type GymConfig, type GymPlan, type GymPurchase, type GymSetup } from '../services/gymApi'

const newPlan = (): GymPlan => ({ id: crypto.randomUUID(), kind: 'gym', name: '', terms: '', amount_paise: 10000, duration_months: 1, sessions: null, active: true, trainer_relationship_id: null, trainer_name: '' })
export default function GymSetupPage() {
  const [setup, setSetup] = useState<GymSetup | null>(null)
  const [draft, setDraft] = useState<GymConfig | null>(null)
  const [registrations, setRegistrations] = useState<GymPurchase[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [confirm, setConfirm] = useState(false)
  async function load() {
    setBusy(true); setError('')
    try {
      const [data, purchases] = await Promise.all([gymRequest<GymSetup>('/gym/setup'), gymRequest<GymPurchase[]>('/gym/registrations')])
      setSetup(data); setDraft(structuredClone(data.configuration)); setRegistrations(purchases)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load gym setup.') }
    finally { setBusy(false) }
  }
  useEffect(() => { void load() }, [])
  async function save() {
    if (!setup || !draft) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await gymRequest<GymSetup>('/gym/setup', jsonRequest('PUT', { revision: setup.revision, configuration: draft, confirm_payment: true }))
      setSetup(result); setDraft(structuredClone(result.configuration)); setConfirm(false); setMessage('Gym setup saved. Existing registrations keep their original terms and payment instructions.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to save gym setup.'); setConfirm(false) }
    finally { setBusy(false) }
  }
  async function upload(kind: 'logo' | 'payment_qr', file?: File) {
    if (!file || !draft) return
    if (file.size > 2 * 1024 * 1024) { setError('Choose a PNG or JPEG up to 2 MB.'); return }
    setBusy(true); setError('')
    try {
      const form = new FormData(); form.append('file', file)
      const result = await gymRequest<{ id: string }>(`/gym/assets/${kind}`, { method: 'POST', body: form })
      setDraft(current => current && (kind === 'logo' ? { ...current, logo_id: result.id } : { ...current, payment: { ...current.payment, qr_asset_id: result.id } }))
      setMessage('Image uploaded for preview. Review and save to publish it.')
    } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed.') }
    finally { setBusy(false) }
  }
  async function download(format: 'qr.png' | 'poster.pdf') {
    setError(''); setBusy(true)
    try { await downloadRegistration(format) } catch (err) { setError(err instanceof Error ? err.message : 'Download failed.') }
    finally { setBusy(false) }
  }
  function updatePlan(id: string, change: Partial<GymPlan>) { setDraft(current => current && ({ ...current, plans: current.plans.map(p => p.id === id ? { ...p, ...change } : p) })) }
  return <main className="page-content gym-setup">
    <PageHeader eyebrow="Gym operations" title="Set the stage for every member" description="Publish your gym, plans and registration link. Payments go directly to your gym." />
    {error && <div className="gym-notice" role="alert">{error} <Button variant="secondary" disabled={busy} onClick={() => void load()}>Reload saved setup</Button></div>}
    {message && <p role="status">{message}</p>}
    {!draft || !setup ? (busy ? <Skeleton label="Loading gym setup…" /> : <EmptyState title="Gym setup unavailable">Try reloading your saved setup.</EmptyState>) : <>
      <form onSubmit={event => { event.preventDefault(); setError(''); setConfirm(true) }}>
        <fieldset disabled={busy} className="gym-fieldset">
          <Card><h2>01 / Your gym</h2><div className="gym-form-grid">
            <label>Public gym name<input required maxLength={120} value={draft.display_name} onChange={e => setDraft({ ...draft, display_name: e.target.value })} /></label>
            <label>Public contact phone<input type="tel" maxLength={40} value={draft.contact_phone} onChange={e => setDraft({ ...draft, contact_phone: e.target.value })} /></label>
            <label className="gym-wide">About your gym<textarea maxLength={1200} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} /></label>
            <label className="gym-wide">Address<textarea maxLength={500} value={draft.address} onChange={e => setDraft({ ...draft, address: e.target.value })} /></label>
            <label>Gym logo · PNG or JPEG, up to 2 MB<input type="file" accept="image/png,image/jpeg" onChange={e => { void upload('logo', e.target.files?.[0]); e.target.value = '' }} /></label>
            {draft.logo_id && <div><ProtectedImage className="gym-logo" src={privateGymAsset(draft.logo_id)} alt="Gym logo preview" /><Button variant="tertiary" onClick={() => setDraft({ ...draft, logo_id: null })}>Remove logo</Button></div>}
          </div></Card>
          <Card><h2>02 / Gym and personal training plans</h2><p>Fixed-duration plans renew manually. PT plans belong to one trainer; a per-session plan covers one session.</p>
            {draft.plans.map((plan, index) => <section key={plan.id} className="gym-plan-editor" aria-label={`Plan ${index + 1}`}><div className="gym-form-grid">
              <label>Plan name<input required maxLength={120} value={plan.name} onChange={e => updatePlan(plan.id, { name: e.target.value })} /></label>
              <label>Type<select value={plan.kind} onChange={e => updatePlan(plan.id, { kind: e.target.value as GymPlan['kind'], duration_months: 1, sessions: null, trainer_relationship_id: null, trainer_name: '' })}><option value="gym">Gym membership</option><option value="pt">Personal training</option></select></label>
              <label>Duration<select value={plan.sessions ? 'session' : String(plan.duration_months)} onChange={e => updatePlan(plan.id, { duration_months: e.target.value === 'session' ? null : Number(e.target.value), sessions: e.target.value === 'session' ? 1 : null })}>{[1, 3, 6, 12].map(months => <option key={months} value={months}>{months} month{months > 1 ? 's' : ''}</option>)}{plan.kind === 'pt' && <option value="session">One session</option>}</select></label>
              <label>Price (₹)<input type="number" required min="0.01" max="1000000" step="0.01" value={plan.amount_paise / 100} onChange={e => updatePlan(plan.id, { amount_paise: Math.round(Number(e.target.value) * 100) })} /></label>
              {plan.kind === 'pt' && <><label>Trainer account<select required value={plan.trainer_relationship_id ?? ''} onChange={e => updatePlan(plan.id, { trainer_relationship_id: Number(e.target.value) })}><option value="">Select a trainer</option>{setup.trainers.map(trainer => <option key={trainer.id} value={trainer.id}>{trainer.email}</option>)}</select></label><label>Trainer name shown publicly<input required maxLength={120} value={plan.trainer_name} onChange={e => updatePlan(plan.id, { trainer_name: e.target.value })} /></label></>}
              <label className="gym-wide">Plan terms and inclusions<textarea required maxLength={2000} value={plan.terms} onChange={e => updatePlan(plan.id, { terms: e.target.value })} /></label>
              <label className="gym-checkbox"><input type="checkbox" checked={plan.active} onChange={e => updatePlan(plan.id, { active: e.target.checked })} />Offer this plan</label>
              <Button variant="tertiary" onClick={() => setDraft({ ...draft, plans: draft.plans.filter(p => p.id !== plan.id) })}>Remove from catalogue</Button>
            </div></section>)}
            <Button variant="secondary" disabled={draft.plans.length >= 100} onClick={() => setDraft({ ...draft, plans: [...draft.plans, newPlan()] })}>Add plan</Button>
          </Card>
          <Card><h2>03 / Gym payment destination</h2><p>This is your gym’s payment QR. It is separate from the registration QR and your Vectra software subscription.</p>
            {!setup.can_edit_payment && <p>Only the gym owner can change these payment details.</p>}
            <fieldset disabled={!setup.can_edit_payment} className="gym-fieldset gym-form-grid">
              <label>Recipient name<input maxLength={120} value={draft.payment.recipient_name} onChange={e => setDraft({ ...draft, payment: { ...draft.payment, recipient_name: e.target.value } })} /></label>
              <label>UPI ID<input maxLength={120} value={draft.payment.upi_id} onChange={e => setDraft({ ...draft, payment: { ...draft.payment, upi_id: e.target.value } })} /></label>
              <label>Payment QR · PNG or JPEG, up to 2 MB<input type="file" accept="image/png,image/jpeg" onChange={e => { void upload('payment_qr', e.target.files?.[0]); e.target.value = '' }} /></label>
              {draft.payment.qr_asset_id && <ProtectedImage className="gym-payment-qr" src={privateGymAsset(draft.payment.qr_asset_id)} alt="Payment QR preview: verify it matches the recipient and UPI ID" />}
            </fieldset>
          </Card>
          <Card><h2>04 / Registration availability</h2><label className="gym-checkbox"><input type="checkbox" checked={draft.registration_enabled} onChange={e => setDraft({ ...draft, registration_enabled: e.target.checked })} />Accept new registrations</label><p>Turning this off preserves your printed QR and existing registrations. Visitors will see a registration unavailable message.</p><Button type="submit">Review and save setup</Button></Card>
        </fieldset>
      </form>
      <Card><h2>Your permanent registration link</h2>{setup.join_url ? <><a className="gym-share-link" href={setup.join_url} target="_blank" rel="noreferrer">{setup.join_url}</a><p>Renaming your gym will not change this link or the printed QR.</p><div className="gym-actions"><Button disabled={busy} variant="secondary" onClick={() => void navigator.clipboard.writeText(setup.join_url!).then(() => setMessage('Registration link copied.')).catch(() => setError('Copy the registration link shown above.'))}>Copy link</Button><Button disabled={busy} variant="secondary" onClick={() => void download('qr.png')}>Download registration QR</Button><Button disabled={busy} onClick={() => void download('poster.pdf')}>Download reception poster</Button></div></> : <p>Save your gym setup to generate the link. The server’s public web URL must be configured before downloads are available.</p>}</Card>
      <Card><h2>Payment verification queue</h2><p>Pending submissions are not confirmed collections. PT eligibility and capacity are rechecked at confirmation; late payments can require reassignment or an external refund.</p>{registrations.filter(p => !['confirmed', 'refunded', 'superseded', 'cancelled'].includes(p.status)).map(p => <MembershipPayment key={p.id} purchase={p} admin trainers={setup.trainers} onChange={updated => setRegistrations(rows => rows.map(row => row.id === updated.id ? updated : row))} />)}</Card>
      <Card><h2>Confirmed collections and history</h2><p>Manually verified records, not a live bank balance. Open a record to see refunds and membership consequences.</p>{registrations.filter(p => ['confirmed', 'refunded', 'superseded', 'cancelled'].includes(p.status)).map(p => <MembershipPayment key={p.id} purchase={p} admin trainers={setup.trainers} onChange={updated => setRegistrations(rows => rows.map(row => row.id === updated.id ? updated : row))} />)}<p>Showing latest 100 registrations.</p></Card>
      <Card><h2>Setup change history</h2>{setup.audit.length ? <ul>{setup.audit.map(change => <li key={change.revision}>Revision {change.revision} · User {change.actor_user_id} · {new Date(change.created_at).toLocaleString()}</li>)}</ul> : <p>No published changes yet.</p>}</Card>
      <Dialog open={confirm} title="Review gym setup before publishing" onClose={() => { if (!busy) setConfirm(false) }}>
        <h3>{draft.display_name}</h3><p>{draft.plans.filter(p => p.active).length} available plans · Registration {draft.registration_enabled ? 'open' : 'paused'}</p>
        <h3>Confirm payment destination</h3><p><strong>{draft.payment.recipient_name || 'Not set'}</strong><br />{draft.payment.upi_id || 'No UPI ID'}</p>
        {draft.payment.qr_asset_id && <ProtectedImage className="gym-payment-qr" src={privateGymAsset(draft.payment.qr_asset_id)} alt="Confirm gym payment QR" />}
        <p>Check that this QR belongs to the recipient and UPI ID above. These instructions will be shown publicly. Existing pending registrations keep their original details until the member explicitly reviews a replacement.</p>
        <div className="gym-actions"><Button disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Confirm and publish'}</Button><Button disabled={busy} variant="secondary" onClick={() => setConfirm(false)}>Back to editing</Button></div>
      </Dialog>
    </>}
  </main>
}
