import { features } from '../services/features'
import { BarChart3, CalendarDays, LayoutDashboard, Settings, TrendingUp, UsersRound, ArrowUpRight, Bell } from 'lucide-react'
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
] as const
export default function SideNav({ activeTab, onTabChange, memberAction }: { activeTab: AppTab; onTabChange: (tab: AppTab) => void; memberAction?: () => void }) {
  const business = useBusiness()
  const admin = business?.staff_roles.some(role => role === 'owner' || role === 'admin')
  return <aside className="side-nav"><div className="side-brand"><span className="brand-symbol" aria-hidden="true">V</span><strong>Vectra<span>PERFORMANCE OS</span></strong></div>
    <p className="nav-caption">{admin ? 'Business workspace' : 'Coaching workspace'}</p>
    <nav aria-label="Primary navigation">{items.filter(item => features.formAnalysis || item.tab !== 'recent-analysis').filter(item => item.tab === 'gym-setup' ? admin && business?.organization_type === 'gym' : admin || !['settings', 'insights'].includes(item.tab)).map(({ tab, label, Icon }) => <button key={tab} aria-current={activeTab === tab ? 'page' : undefined} onClick={() => onTabChange(tab)}><Icon size={19} strokeWidth={1.8} /><span>{label}</span></button>)}</nav>
    {memberAction && <button className="member-link" onClick={memberAction}><ArrowUpRight size={18} /> My member profile</button>}
    <div className="side-footer"><span className="eyebrow">Built for progress</span><p>One workspace.<br />Every next step.</p></div>
  </aside>
}
