import { Button, Dialog, PageHeader } from '../design-system/components'
import { useEffect, useState } from 'react'
import { API_BASE_URL } from '../services/apiConfig'
import { buildAuthHeaders } from '../services/session'
import { listClients } from '../services/clientApi'
import { useBusiness } from '../components/BusinessContext'
import type { Client } from '../types/client'

type Invitation = { id: string; email: string; role: string; expires_at: string; consumed_at: string | null; revoked_at: string | null; delivery_status: string; attempts: number; error_code: string | null }
type Person = { id: number; email: string; status: string; roles: string[] }
export default function AccessPage() {
  const business = useBusiness()!
  const [removal, setRemoval] = useState<{ id: number; email: string; role: string } | null>(null)
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('trainer')
  const [inviteClient, setInviteClient] = useState('')
  const [people, setPeople] = useState<Person[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [clientId, setClientId] = useState('')
  const [trainerId, setTrainerId] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    Promise.all([fetch(`${API_BASE_URL}/organization/people`, { headers: buildAuthHeaders() }).then(async response => {
      if (!response.ok) throw new Error('Business access is unavailable')
      return await response.json() as Person[]
    }), listClients(), fetch(`${API_BASE_URL}/organization/invitations`, { headers: buildAuthHeaders() }).then(async response => {
      if (!response.ok) throw new Error('Unable to load invitations')
      return await response.json() as Invitation[]
    })]).then(([staff, records, invites]) => { if (active) { setPeople(staff); setClients(records); setInvitations(invites) } })
      .catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [revision])
  async function change(path: string, method: string, body?: object) {
    setBusy(true); setError('')
    try {
      const response = await fetch(`${API_BASE_URL}${path}`, { method, headers: buildAuthHeaders({ 'Content-Type': 'application/json' }), body: body ? JSON.stringify(body) : undefined })
      if (!response.ok) throw new Error((await response.json()).detail || 'Update failed')
      setRevision(value => value + 1)
    } catch (err) { setError(err instanceof Error ? err.message : 'Update failed') }
    finally { setBusy(false) }
  }
  return <main className="member-home"><PageHeader eyebrow="Business / people" title="A team built for progress." description={`Manage staff and client assignments in ${business.name}. Role changes apply only to this business.`} />
    {error && <p role="alert">{error}</p>}
    <section className="workspace-card"><h2>Invite staff or a coaching client</h2><p>Invitations expire after 3 days. Client invitations link an existing profile after email ownership is verified; they grant no staff permissions. Only owners can invite admins.</p>
      <form className="invitation-form" onSubmit={event => { event.preventDefault(); void change('/organization/invitations', 'POST', { email: inviteEmail, role: inviteRole, client_id: inviteRole === 'client' ? Number(inviteClient) : null }) }}>
        <label>Email address<input type="email" required maxLength={254} value={inviteEmail} onChange={event => setInviteEmail(event.target.value)} /></label>
        <label>Role<select value={inviteRole} onChange={event => setInviteRole(event.target.value)}><option value="trainer">Trainer</option><option value="client">Coaching client</option>{business.staff_roles.includes('owner') && <option value="admin">Admin</option>}</select></label>
        {inviteRole === 'client' && <label>Coaching profile<select required value={inviteClient} onChange={event => setInviteClient(event.target.value)}><option value="">Choose an unlinked profile</option>{clients.filter(client => client.is_active).map(client => <option key={client.id} value={client.id}>{client.first_name} {client.last_name}</option>)}</select></label>}
        <button disabled={busy || (inviteRole === 'client' && !inviteClient)}>Send invitation</button>
      </form>
      {!invitations.length && <p>No invitations yet.</p>}
      {invitations.map(invite => <article key={invite.id}><strong>{invite.email}</strong><p>{invite.role} · {invite.consumed_at ? 'Accepted' : invite.revoked_at ? 'Revoked' : new Date(invite.expires_at) <= new Date() ? 'Expired' : 'Awaiting acceptance'} · Email: {invite.delivery_status === 'sent' ? 'Submitted to email provider' : invite.delivery_status}</p><p>Expires {new Date(invite.expires_at).toLocaleString()}{invite.error_code ? ' · Delivery needs attention. Contact support or send a replacement invitation.' : ''}</p>
        {!invite.consumed_at && !invite.revoked_at && (invite.role !== 'admin' || business.staff_roles.includes('owner')) && <button data-variant="danger" disabled={busy} onClick={() => void change(`/organization/invitations/${invite.id}`, 'DELETE')}>Revoke invitation</button>}
      </article>)}
    </section>
    <section className="workspace-card"><h2>People</h2>{people.map(person => <article key={person.id}><strong>{person.email}</strong><p>{person.status} · {person.roles.join(', ') || 'Member / account'}</p>{person.roles.filter(role => role === 'trainer' || (role === 'admin' && business.staff_roles.includes('owner'))).map(role => <Button variant="danger" disabled={busy} key={role} onClick={() => setRemoval({ id: person.id, email: person.email, role })}>Remove {role} access</Button>)}</article>)}</section>
    <section className="workspace-card"><h2>Client assignments</h2><label>Client <select value={clientId} onChange={event => setClientId(event.target.value)}><option value="">Choose client</option>{clients.map(client => <option key={client.id} value={client.id}>{client.first_name} {client.last_name}</option>)}</select></label>
      <label>Staff <select value={trainerId} onChange={event => setTrainerId(event.target.value)}><option value="">Choose staff</option>{people.filter(p => p.status === 'active' && p.roles.length).map(p => <option key={p.id} value={p.id}>{p.email}</option>)}</select></label>
      <button disabled={busy || !clientId || !trainerId} onClick={() => void change(`/clients/${clientId}/trainer-assignment`, 'PUT', { relationship_id: Number(trainerId), active: true })}>Assign</button>
      <button disabled={busy || !clientId || !trainerId} onClick={() => void change(`/clients/${clientId}/trainer-assignment`, 'PUT', { relationship_id: Number(trainerId), active: false })}>End assignment</button>
      <p>Assigning a coach controls access to coaching records. It does not activate a paid package.</p>
    </section><Dialog open={!!removal} title="Remove staff access?" onClose={() => setRemoval(null)}><p>Remove {removal?.role} access for {removal?.email} in {business.name}? Their member profile and other businesses remain available.</p><div className="header-actions"><Button variant="secondary" onClick={() => setRemoval(null)}>Keep access</Button><Button variant="danger" disabled={busy} onClick={() => { if (removal) { void change(`/organization/people/${removal.id}/roles/${removal.role}`, 'DELETE'); setRemoval(null) } }}>Remove role</Button></div></Dialog></main>
}
