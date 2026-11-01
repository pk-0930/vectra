import { features } from '../services/features'
import { BarChart3, CalendarDays, LayoutDashboard, Settings, TrendingUp, UsersRound, ArrowUpRight, Bell, CreditCard, LogOut } from 'lucide-react'
import { useBusiness } from './BusinessContext'
import type { AppTab } from '../types/navigation'
const items = [
  { tab: 'dashboard', label: 'Overview', Icon: LayoutDashboard },
  { tab: 'clients', label: 'Clients', Icon: UsersRound },
  { tab: 'recent-analysis', label: 'Form analysis', Icon: BarChart3 },
  { tab: 'sessions', label: 'Sessions', Icon: CalendarDays },
  { tab: 'insights', label: 'Reports', Icon: TrendingUp },
  { tab: 'inbox', label: 'Inbox', Icon: Bell },
  { tab: 'gym-setup', label: 'Gym setup', Icon: Settings },
  { tab: 'settings', label: 'Business access', Icon: Settings },
  { tab: 'billing', label: 'Billing', Icon: CreditCard },
] as const
type BusinessOption = { organization_id: number; name: string }
export default function SideNav({ activeTab, onTabChange, memberAction, onSignOut, businesses = [], selectedBusiness, onBusinessChange }: { activeTab: AppTab; onTabChange: (tab: AppTab) => void; memberAction?: () => void; onSignOut?: () => void; businesses?: BusinessOption[]; selectedBusiness?: number | null; onBusinessChange?: (id: number) => void }) {
  const business = useBusiness()
  const admin = business?.staff_roles.some(role => role === 'owner' || role === 'admin')
  const role = business?.staff_roles.includes('owner') ? 'Owner' : business?.staff_roles.includes('admin') ? 'Admin' : business?.staff_roles.includes('trainer') ? 'Trainer' : null
  return <aside className="side-nav"><div className="side-brand"><span className="brand-symbol" aria-hidden="true">V</span><strong>Vectra<span>PERFORMANCE OS</span></strong></div>
    <p className="nav-caption">{business?.name || (admin ? 'Business workspace' : 'Coaching workspace')}{role && <span className="nav-role">{role}</span>}</p>
    {businesses.length > 1 && onBusinessChange && <label className="side-business-select">Business<select aria-label="Current business" value={selectedBusiness ?? ''} onChange={event => onBusinessChange(Number(event.target.value))}>{businesses.map(item => <option key={item.organization_id} value={item.organization_id}>{item.name}</option>)}</select></label>}
    <nav aria-label="Primary navigation">{items.filter(item => features.formAnalysis || item.tab !== 'recent-analysis').filter(item => item.tab === 'gym-setup' ? admin && business?.organization_type === 'gym' : item.tab === 'billing' ? business?.staff_roles.includes('owner') : admin || !['settings', 'insights'].includes(item.tab)).map(({ tab, label, Icon }) => <button key={tab} aria-current={activeTab === tab ? 'page' : undefined} onClick={() => onTabChange(tab)}><Icon size={19} strokeWidth={1.8} /><span>{label}</span></button>)}</nav>
    {memberAction && <button className="member-link" onClick={memberAction}><ArrowUpRight size={18} /> My member profile</button>}
    {onSignOut && <button className="member-link" onClick={onSignOut}><LogOut size={18} /> Sign out</button>}
  </aside>
}
