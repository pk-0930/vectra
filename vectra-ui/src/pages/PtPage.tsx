import { useEffect, useState } from 'react'
import { gymRequest, jsonRequest } from '../services/gymApi'
import { Button, Card } from '../design-system/components'

type Entitlement = { purchase_id: string; client_id: number; trainer_relationship_id: number; trainer_name: string; first_name: string; last_name: string; starts_on: string; ends_before: string; remaining_sessions: number | null; revoked_at: string | null; needs_reassignment: boolean }
type Appointment = { id: string; first_name: string; last_name: string; starts_at: string; ends_at: string; status: string; version: number; trainer_relationship_id: number; trainer_name: string }
type Workspace = { entitlements: Entitlement[]; appointments: Appointment[]; trainers: { id: number; email?: string; name?: string }[]; clients: { id: number; first_name: string; last_name: string }[]; admin: boolean; can_complete: boolean; organization_type: string }
export default function PtPage() {
  const [data, setData] = useState<Workspace | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [entitlement, setEntitlement] = useState('')
  const [client, setClient] = useState('')
  const [trainer, setTrainer] = useState('')
  const [start, setStart] = useState('')
  const [consent, setConsent] = useState(false)
  const [note, setNote] = useState('')
  const [requestId, setRequestId] = useState(crypto.randomUUID())
  useEffect(() => { let active = true; gymRequest<Workspace>('/pt/workspace').then(row => { if (active) setData(row) }).catch(err => { if (active) setError(err.message) }); return () => { active = false } }, [])
  async function run(path: string, payload: unknown) {
    setBusy(true); setError('')
    try { await gymRequest(path, jsonRequest('POST', payload)); setData(await gymRequest<Workspace>('/pt/workspace')); setRequestId(crypto.randomUUID()) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to update PT appointments.') }
    finally { setBusy(false) }
  }
  const timestamp = () => start ? `${start}:00+05:30` : ''
  const time = (value: string) => new Date(value).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })
  return <section className="member-home" aria-label="PT packages and appointments"><h1>PT packages and appointments</h1>{error && <p role="alert">{error}</p>}
    <p>All appointment times are India time. Sessions last 60 minutes. Cancellation does not consume credit; staff completion after the session does. Duration packages allow one session per day.</p>
    <Card><h2>Book or reschedule</h2>{data?.organization_type === 'gym' ? <label>Paid PT package<select value={entitlement} onChange={e => { setEntitlement(e.target.value); setRequestId(crypto.randomUUID()) }}><option value="">Select a package</option>{data.entitlements.filter(e => !e.revoked_at && e.remaining_sessions !== 0 && !e.needs_reassignment).map(e => <option key={e.purchase_id} value={e.purchase_id}>{e.first_name} {e.last_name} · {e.trainer_name} · ends before {e.ends_before}</option>)}</select></label> : <><label>Client<select value={client} onChange={e => { setClient(e.target.value); setRequestId(crypto.randomUUID()) }}><option value="">Select client</option>{data?.clients.map(c => <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>)}</select></label><label>Assigned coach<select value={trainer} onChange={e => { setTrainer(e.target.value); setRequestId(crypto.randomUUID()) }}><option value="">Select assigned coach</option>{data?.trainers.map(t => <option key={t.id} value={t.id}>{t.name || t.email || `Coach ${t.id}`}</option>)}</select></label><p>Independent coaching does not require gym membership or use the gym’s 10-client limit.</p></>}
      <label>Start time (India)<input type="datetime-local" value={start} onChange={e => { setStart(e.target.value); setRequestId(crypto.randomUUID()) }} /></label><Button disabled={busy || !start || !(entitlement || (client && trainer))} onClick={() => void run('/appointments', { request_id: requestId, entitlement_id: entitlement || null, client_id: client ? Number(client) : null, trainer_relationship_id: trainer ? Number(trainer) : null, starts_at: timestamp() })}>Book appointment</Button><p>To reschedule, enter the new time above and choose Reschedule on the appointment below.</p>
    </Card>
    <Card><h2>PT entitlements</h2>{data?.entitlements.map(e => <article key={e.purchase_id}><strong>{e.first_name} {e.last_name}</strong><p>{e.starts_on} to before {e.ends_before} · {e.trainer_name} · {e.remaining_sessions === null ? 'Duration package' : `${e.remaining_sessions} session credit`} {e.revoked_at ? '· Revoked' : ''}</p>{e.needs_reassignment && <p role="status">Trainer removed or inactive: administrator reassignment required. History is preserved.</p>}{data.admin && !e.revoked_at && <Button variant="secondary" disabled={busy || !trainer || !consent || !note} onClick={() => void run(`/gym/purchases/${e.purchase_id}/reassign-pt`, { trainer_relationship_id: Number(trainer), member_consent: consent, note })}>Reassign with recorded consent</Button>}</article>)}{data?.admin && <><h3>Reassignment details</h3><label>Replacement trainer<select value={trainer} onChange={e => setTrainer(e.target.value)}><option value="">Select trainer</option>{data.trainers.map(t => <option key={t.id} value={t.id}>{t.name || t.email || `Coach ${t.id}`}</option>)}</select></label><label>Consent record / reason<textarea maxLength={2000} value={note} onChange={e => setNote(e.target.value)} /></label><label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />Member agreed to this reassignment and rebooking</label><p>Reassignment cancels this package’s bookings without consuming credit. Rebook with the replacement trainer.</p></>}</Card>
    <Card><h2>Appointments</h2>{data?.appointments.map(a => <article key={a.id}><strong>{a.first_name} {a.last_name}</strong><p>{time(a.starts_at)}–{time(a.ends_at)} IST · {a.status} · {a.trainer_name}</p>{a.status === 'booked' && <><Button variant="secondary" disabled={busy || !start} onClick={() => void run(`/appointments/${a.id}/reschedule`, { version: a.version, starts_at: timestamp() })}>Reschedule</Button><Button variant="secondary" disabled={busy} onClick={() => void run(`/appointments/${a.id}/cancel`, { version: a.version })}>Cancel without consuming credit</Button>{data.can_complete && <Button disabled={busy || new Date(a.ends_at) > new Date()} onClick={() => void run(`/appointments/${a.id}/complete`, { version: a.version })}>Complete session</Button>}</>}</article>)}{data?.appointments.length === 0 && <p>No appointments yet.</p>}<p>Showing latest 200 records.</p></Card>
  </section>
}
