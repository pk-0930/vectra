import { useEffect, useState } from 'react'
import { useBusiness } from '../components/BusinessContext'
import { Button, PageHeader } from '../design-system/components'
import { rupees } from '../services/gymApi'
import { fetchReport, setPurchasesEnabled } from '../services/workspaceApi'
import type { Report } from '../services/workspaceApi'
const indiaToday = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
export default function ReportsPage() {
  const business = useBusiness()!
  const [start, setStart] = useState(() => `${indiaToday().slice(0, 7)}-01`)
  const [end, setEnd] = useState(indiaToday)
  const [data, setData] = useState<Report | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    fetchReport(start, end).then(value => { if (active) { setData(value); setError('') } }).catch(err => { if (active) { setData(null); setError(err.message) } })
    return () => { active = false }
  }, [start, end, revision])
  async function toggle() {
    if (!data) return
    setBusy(true); setError('')
    try { await setPurchasesEnabled(!data.purchases_enabled); setRevision(value => value + 1) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to change availability.') }
    finally { setBusy(false) }
  }
  const total = data?.collections.reduce((sum, row) => sum + row.amount_paise, 0) ?? 0
  const refunds = data?.refunds.filter(row => row.verified_collection).reduce((sum, row) => sum + row.amount_paise, 0) ?? 0
  return <section className="page-content">
    <PageHeader eyebrow={business.name} title="Business reports" description="Verified gym collections and recorded refunds. These are not accounting revenue, a live bank balance or automatic bank reconciliation." />
    <div className="workspace-shortcuts"><label>From<input type="date" value={start} onChange={event => setStart(event.target.value)} /></label><label>Through<input type="date" value={end} onChange={event => setEnd(event.target.value)} /></label><Button onClick={() => setRevision(value => value + 1)}>Refresh</Button></div>
    {error && <p role="alert">{error}</p>}
    {data && <>
      <div className="member-grid"><section className="workspace-card"><h2>Confirmed collections</h2><strong>{rupees(total)}</strong>{data.collections.map(row => <p key={row.method}>{row.method.toUpperCase()}: {rupees(row.amount_paise)} · {row.payments} receipts</p>)}</section>
      <section className="workspace-card"><h2>Recorded refunds</h2>{data.refunds.length === 0 && <p>No refunds in this period.</p>}{data.refunds.map(row => <p key={String(row.verified_collection)}>{row.verified_collection ? 'Previously verified collections' : 'Receipts never confirmed in Vectra'}: {rupees(row.amount_paise)} · {row.refunds} refunds</p>)}<p>Net verified collections: {rupees(total - refunds)}</p></section>
      <section className="workspace-card"><h2>Memberships today</h2><p>{data.memberships.active_members} active members</p><p>{data.memberships.expiring_members} expiring within 7 days without a recorded extension</p><small>As of {data.as_of} in India; independent of the report date range.</small></section></div>
      <section className="workspace-card"><h2>PT purchases created in this period</h2>{data.pt_purchases.length === 0 ? <p>No PT purchases.</p> : <div className="report-table-scroll"><table><thead><tr><th>Status</th><th>Purchases</th><th>PT value</th></tr></thead><tbody>{data.pt_purchases.map(row => <tr key={row.status}><td>{row.status.replaceAll('_', ' ')}</td><td>{row.purchases}</td><td>{rupees(row.amount_paise)}</td></tr>)}</tbody></table></div>}<p>Purchase value is not collected money. Collections use receipt dates; refunds use the date recorded in Vectra. All dates use India time.</p></section>
      {business.organization_type === 'gym' && business.staff_roles.includes('owner') && <section className="workspace-card"><h2>Purchase availability</h2><p>New gym and PT purchases are {data.purchases_enabled ? 'enabled' : 'paused'}. Pausing preserves existing records, paid access and payment resolution.</p><Button variant="secondary" disabled={busy} onClick={() => void toggle()}>{data.purchases_enabled ? 'Pause new purchases' : 'Enable new purchases'}</Button></section>}
    </>}
  </section>
}
