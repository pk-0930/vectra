import { useEffect, useState } from 'react'
import { Button, Card, Dialog, EmptyState, PageHeader, Skeleton, StatusBadge } from '../design-system/components'
import ProtectedImage from '../components/ProtectedImage'
import { downloadRegistration, gymRequest, jsonRequest, privateGymAsset, type GymConfig, type GymPlan, type GymSetup } from '../services/gymApi'

const newPlan = (): GymPlan => ({ id: crypto.randomUUID(), kind: 'gym', name: '', terms: '', amount_paise: 10000, duration_months: 1, sessions: null, active: true, trainer_relationship_id: null, trainer_name: '' })
export default function GymSetupPage({ onGymNameChange, refreshBilling }: { onGymNameChange?: (name: string) => void; refreshBilling?: () => Promise<void> }) {
  const [setup, setSetup] = useState<GymSetup | null>(null)
  const [draft, setDraft] = useState<GymConfig | null>(null)
  const [step, setStep] = useState(0)
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [planError, setPlanError] = useState('')
  const [registrationError, setRegistrationError] = useState('')
  const [assetErrors, setAssetErrors] = useState<Partial<Record<'logo' | 'payment_qr', string>>>({})
  const [message, setMessage] = useState('')
  const [confirm, setConfirm] = useState(false)
  async function load() {
    setBusy(true); setError('')
    try {
      const data = await gymRequest<GymSetup>('/gym/setup')
      setSetup(data); setDraft(structuredClone(data.configuration)); setExpandedPlanId(data.configuration.plans[0]?.id ?? null)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to load gym setup.') }
    finally { setBusy(false) }
  }
  useEffect(() => { void load() }, [])
  async function save() {
    if (!setup || !draft) return
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await gymRequest<GymSetup>('/gym/setup', jsonRequest('PUT', { revision: setup.revision, configuration: draft, confirm_payment: true }))
      setSetup(result); setDraft(structuredClone(result.configuration)); setConfirm(false); onGymNameChange?.(result.configuration.display_name); if (refreshBilling) void refreshBilling().catch(() => {}); setMessage('Gym setup saved. Existing registrations keep their original terms and payment instructions.')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to save gym setup.'
      if (message.startsWith('Before accepting registrations')) setRegistrationError(message)
      else setError(message)
      setConfirm(false)
    }
    finally { setBusy(false) }
  }
  async function upload(kind: 'logo' | 'payment_qr', file?: File) {
    if (!file || !draft) return
    setAssetErrors(current => ({ ...current, [kind]: '' }))
    if (file.size > 2 * 1024 * 1024) { setAssetErrors(current => ({ ...current, [kind]: 'Choose a PNG or JPEG up to 2 MB.' })); return }
    setBusy(true); setError('')
    try {
      const form = new FormData(); form.append('file', file)
      const result = await gymRequest<{ id: string }>(`/gym/assets/${kind}`, { method: 'POST', body: form })
      setDraft(current => current && (kind === 'logo' ? { ...current, logo_id: result.id } : { ...current, payment: { ...current.payment, qr_asset_id: result.id } }))
      setMessage('Image uploaded for preview. Review and save to publish it.')
    } catch (err) { setAssetErrors(current => ({ ...current, [kind]: err instanceof Error ? err.message : 'Upload failed.' })) }
    finally { setBusy(false) }
  }
  async function download(format: 'qr.png' | 'poster.pdf') {
    setError(''); setBusy(true)
    try { await downloadRegistration(format) } catch (err) { setError(err instanceof Error ? err.message : 'Download failed.') }
    finally { setBusy(false) }
  }
  function updatePlan(id: string, change: Partial<GymPlan>) { setDraft(current => current && ({ ...current, plans: current.plans.map(p => p.id === id ? { ...p, ...change } : p) })) }
  const registrationRequirements = draft ? [
    [draft.plans.some(plan => plan.kind === 'gym' && plan.active), 'At least one available gym membership plan'],
    [Boolean(draft.payment.recipient_name.trim()), 'Payment recipient name'],
    [Boolean(draft.payment.upi_id.trim()), 'Payment UPI ID'],
    [Boolean(draft.payment.qr_asset_id), 'Uploaded gym payment QR'],
  ] as const : []
  const registrationReady = registrationRequirements.every(([ready]) => ready)
  const setupPublished = Boolean(setup && setup.revision > 0)
  const hasChanges = Boolean(draft && setup && JSON.stringify(draft) !== JSON.stringify(setup.configuration))
  const savedConfiguration = setup?.configuration
  const savedPlanStepComplete = Boolean(setupPublished && savedConfiguration?.plans.length && savedConfiguration.plans.every(plan => plan.name.trim() && plan.terms.trim() && plan.amount_paise > 0 && (plan.kind !== 'pt' || (plan.trainer_relationship_id && plan.trainer_name.trim()))))
  const savedStepsComplete = [
    Boolean(setupPublished && savedConfiguration?.display_name.trim()),
    savedPlanStepComplete,
    Boolean(setupPublished && savedConfiguration?.payment.recipient_name.trim() && savedConfiguration.payment.upi_id.trim() && savedConfiguration.payment.qr_asset_id),
    setupPublished,
  ]
  return <main className="page-content gym-setup">
    <PageHeader eyebrow="Gym operations" title="Set the stage for every member" description="Publish your gym, plans and registration link. Payments go directly to your gym." />
    {error && <div className="gym-notice" role="alert">{error} <Button variant="secondary" disabled={busy} onClick={() => void load()}>Reload saved setup</Button></div>}
    {message && <p role="status">{message}</p>}
    {!draft || !setup ? (busy ? <Skeleton label="Loading gym setup…" /> : <EmptyState title="Gym setup unavailable">Try reloading your saved setup.</EmptyState>) : <>
      <nav className="gym-setup-steps" aria-label="Gym setup progress">{['Gym profile', 'Plans', 'Payment', 'Registration'].map((label, index) => { const current = index === step; const complete = index < step || savedStepsComplete[index]; const stateClass = [current && 'active', complete && 'complete', !current && !complete && 'upcoming'].filter(Boolean).join(' '); return <button type="button" key={label} disabled={index > step && !setupPublished} className={stateClass} aria-current={current ? 'step' : undefined} onClick={() => setStep(index)}><span aria-hidden="true">{complete ? '✓' : index + 1}</span>{label}</button> })}</nav>
      <form onSubmit={event => { event.preventDefault(); setError(''); setRegistrationError(''); if (step === 1) { const invalid = draft.plans.find(plan => !plan.name.trim() || !plan.terms.trim() || plan.amount_paise < 1 || plan.amount_paise > 100000000 || (plan.kind === 'pt' && (!setup.trainers.some(trainer => trainer.id === plan.trainer_relationship_id) || !plan.trainer_name.trim()))); if (invalid) { setPlanError('Complete the required details for each plan before continuing.'); setExpandedPlanId(invalid.id); return } setPlanError('') } if (step < 3) setStep(value => value + 1); else setConfirm(true) }}>
        <fieldset disabled={busy} className="gym-fieldset">
          {step === 0 && <Card><h2>Your gym profile</h2><p>These details appear on your public registration page.</p><div className="gym-form-grid">
            <label>Gym name<input required maxLength={120} value={draft.display_name} onChange={e => setDraft({ ...draft, display_name: e.target.value })} /></label>
            <label>Public contact phone<input type="tel" maxLength={40} value={draft.contact_phone} onChange={e => setDraft({ ...draft, contact_phone: e.target.value })} /></label>
            <label className="gym-wide">About your gym<textarea maxLength={1200} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} /></label>
            <label className="gym-wide">Address<textarea maxLength={500} value={draft.address} onChange={e => setDraft({ ...draft, address: e.target.value })} /></label>
            <label>Gym logo · PNG or JPEG, up to 2 MB<input type="file" accept="image/png,image/jpeg" aria-describedby={assetErrors.logo ? 'gym-logo-error' : undefined} onChange={e => { void upload('logo', e.target.files?.[0]); e.target.value = '' }} />{assetErrors.logo && <span id="gym-logo-error" className="gym-field-error" role="alert">{assetErrors.logo}</span>}</label>
            {draft.logo_id && <div><ProtectedImage className="gym-logo" src={privateGymAsset(draft.logo_id)} alt="Gym logo preview" /><Button variant="tertiary" onClick={() => setDraft({ ...draft, logo_id: null })}>Remove logo</Button></div>}
          </div></Card>}
          {step === 1 && <Card><h2>Plans and pricing</h2><p>Fixed-duration plans renew manually. PT plans belong to one trainer; a per-session plan covers one session.</p>
            {planError && <p className="gym-field-error" role="alert">{planError}</p>}
            {draft.plans.length === 0 && <p>No plans yet. Add a membership or personal training plan to get started.</p>}
            {draft.plans.map((plan, index) => <details key={plan.id} className="gym-plan-editor" open={expandedPlanId === plan.id} onToggle={event => { if ((event.currentTarget as HTMLDetailsElement).open) setExpandedPlanId(plan.id); else if (expandedPlanId === plan.id) setExpandedPlanId(null) }}><summary>{plan.name || `Plan ${index + 1}`} · {plan.kind === 'gym' ? 'Gym membership' : 'Personal training'} · ₹{(plan.amount_paise / 100).toFixed(2)} · {plan.active ? 'Offered' : 'Not offered'}</summary><div className="gym-form-grid">
              <label>Plan name<input required={expandedPlanId === plan.id} maxLength={120} value={plan.name} onChange={e => updatePlan(plan.id, { name: e.target.value })} /></label>
              <label>Type<select value={plan.kind} onChange={e => updatePlan(plan.id, { kind: e.target.value as GymPlan['kind'], duration_months: 1, sessions: null, trainer_relationship_id: null, trainer_name: '' })}><option value="gym">Gym membership</option><option value="pt">Personal training</option></select></label>
              <label>Duration<select value={plan.sessions ? 'session' : String(plan.duration_months)} onChange={e => updatePlan(plan.id, { duration_months: e.target.value === 'session' ? null : Number(e.target.value), sessions: e.target.value === 'session' ? 1 : null })}>{[1, 3, 6, 12].map(months => <option key={months} value={months}>{months} month{months > 1 ? 's' : ''}</option>)}{plan.kind === 'pt' && <option value="session">One session</option>}</select></label>
              <label>Price (₹)<input type="number" required={expandedPlanId === plan.id} min={expandedPlanId === plan.id ? '0.01' : undefined} max={expandedPlanId === plan.id ? '1000000' : undefined} step="0.01" value={plan.amount_paise / 100} onChange={e => updatePlan(plan.id, { amount_paise: Math.round(Number(e.target.value) * 100) })} /></label>
              {plan.kind === 'pt' && <><label>Trainer account<select required={expandedPlanId === plan.id} value={plan.trainer_relationship_id ?? ''} onChange={e => updatePlan(plan.id, { trainer_relationship_id: Number(e.target.value) })}><option value="">Select a trainer</option>{setup.trainers.map(trainer => <option key={trainer.id} value={trainer.id}>{trainer.email}</option>)}</select></label><label>Trainer name shown publicly<input required={expandedPlanId === plan.id} maxLength={120} value={plan.trainer_name} onChange={e => updatePlan(plan.id, { trainer_name: e.target.value })} /></label></>}
              <label className="gym-wide">Plan terms and inclusions<textarea required={expandedPlanId === plan.id} maxLength={2000} value={plan.terms} onChange={e => updatePlan(plan.id, { terms: e.target.value })} /></label>
              <label className="gym-checkbox"><input type="checkbox" checked={plan.active} onChange={e => updatePlan(plan.id, { active: e.target.checked })} />Offer this plan</label>
              <Button variant="tertiary" onClick={() => { setDraft({ ...draft, plans: draft.plans.filter(p => p.id !== plan.id) }); if (expandedPlanId === plan.id) setExpandedPlanId(null) }}>Remove from catalogue</Button>
            </div></details>)}
            <Button variant="secondary" disabled={draft.plans.length >= 100} onClick={() => { const plan = newPlan(); setDraft({ ...draft, plans: [...draft.plans, plan] }); setExpandedPlanId(plan.id) }}>Add plan</Button>
          </Card>}
          {step === 2 && <Card><h2>Payment destination</h2><p>Members will use these details to pay your gym. This is separate from Vectra software billing.</p>
            {!setup.can_edit_payment && <p>Only the gym owner can change these payment details.</p>}
            <fieldset disabled={!setup.can_edit_payment} className="gym-fieldset gym-form-grid">
              <label>Recipient name<input maxLength={120} value={draft.payment.recipient_name} onChange={e => setDraft({ ...draft, payment: { ...draft.payment, recipient_name: e.target.value } })} /></label>
              <label>UPI ID<input maxLength={120} value={draft.payment.upi_id} onChange={e => setDraft({ ...draft, payment: { ...draft.payment, upi_id: e.target.value } })} /></label>
              <label>Payment QR · PNG or JPEG, up to 2 MB<input type="file" accept="image/png,image/jpeg" aria-describedby={assetErrors.payment_qr ? 'gym-payment-qr-error' : undefined} onChange={e => { void upload('payment_qr', e.target.files?.[0]); e.target.value = '' }} />{assetErrors.payment_qr && <span id="gym-payment-qr-error" className="gym-field-error" role="alert">{assetErrors.payment_qr}</span>}</label>
              {draft.payment.qr_asset_id && <ProtectedImage className="gym-payment-qr" src={privateGymAsset(draft.payment.qr_asset_id)} alt="Payment QR preview: verify it matches the recipient and UPI ID" />}
            </fieldset>
          </Card>}
          {step === 3 && <>
            <Card><h2>Registration</h2><p>Review the checklist before accepting new registrations.</p><ul className="gym-readiness-list">{registrationRequirements.map(([ready, label]) => <li key={label}><span aria-hidden="true">{ready ? '✓' : '○'}</span>{label}</li>)}</ul>{registrationError && <p className="gym-field-error" role="alert">{registrationError}</p>}<label className="gym-checkbox"><input type="checkbox" checked={draft.registration_enabled} disabled={!registrationReady && !draft.registration_enabled} onChange={e => { setRegistrationError(''); setDraft({ ...draft, registration_enabled: e.target.checked }) }} />Accept sign-ups</label>{!registrationReady && <p>Complete the checklist before accepting registrations. You can still save your gym profile and plans with registration paused.</p>}</Card>
            <Card><h2>Registration link and materials</h2>{setup.join_url ? <><a className="gym-share-link" href={setup.join_url} target="_blank" rel="noreferrer">{setup.join_url}</a><p>Renaming your gym will not change this link or the printed QR.</p>{hasChanges && <p>Publish your changes before downloading updated registration materials.</p>}<div className="gym-actions"><Button disabled={busy} variant="secondary" onClick={() => void navigator.clipboard.writeText(setup.join_url!).then(() => setMessage('Registration link copied.')).catch(() => setError('Copy the registration link shown above.'))}>Copy link</Button><Button disabled={busy || hasChanges} variant="secondary" onClick={() => void download('qr.png')}>Download registration QR</Button><Button disabled={busy || hasChanges} onClick={() => void download('poster.pdf')}>Download reception poster</Button></div></> : <p>Save setup to generate your permanent link and downloads.</p>}</Card>
          </>}
        </fieldset>
        <div className="gym-wizard-actions"><Button type="button" variant="secondary" disabled={busy || step === 0} onClick={() => setStep(value => Math.max(0, value - 1))}>Back</Button><Button type="submit" disabled={busy}>{step < 3 ? 'Continue' : setupPublished ? 'Review and publish changes' : 'Review and publish'}</Button></div>
      </form>
      <Dialog open={confirm} title="Review gym setup before publishing" onClose={() => { if (!busy) setConfirm(false) }}>
        <h3>{draft.display_name}</h3><p>{draft.plans.filter(p => p.active).length} available plans · <StatusBadge tone={draft.registration_enabled ? 'success' : 'danger'}>Sign-ups {draft.registration_enabled ? 'open' : 'paused'}</StatusBadge></p>
        {draft.plans.filter(p => p.active).length > 0 && <ul>{draft.plans.filter(p => p.active).map(plan => <li key={plan.id}>{plan.name} · ₹{(plan.amount_paise / 100).toFixed(2)} · {plan.kind === 'gym' ? 'Gym membership' : 'Personal training'}</li>)}</ul>}
        <h3>Confirm payment destination</h3><p><strong>{draft.payment.recipient_name || 'Not set'}</strong><br />{draft.payment.upi_id || 'No UPI ID'}</p>
        {draft.payment.qr_asset_id && <ProtectedImage className="gym-payment-qr" src={privateGymAsset(draft.payment.qr_asset_id)} alt="Confirm gym payment QR" />}
        <p>Check that this QR belongs to the recipient and UPI ID above. These instructions will be shown publicly. Existing pending registrations keep their original details until the member explicitly reviews a replacement.</p>
        <div className="gym-actions"><Button disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Confirm and publish'}</Button><Button disabled={busy} variant="secondary" onClick={() => setConfirm(false)}>Back to editing</Button></div>
      </Dialog>
    </>}
  </main>
}
