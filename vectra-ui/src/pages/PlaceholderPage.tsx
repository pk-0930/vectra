import { ArrowRight } from 'lucide-react'
import type { AppTab } from '../types/navigation'
import { Button, Card, EmptyState, PageHeader, StatusBadge } from '../design-system/components'
const copy = { inbox: ['Inbox', 'Your business messages.'], 'gym-setup': ['Gym setup', 'Manage gym registration.'], sessions: ['Sessions', 'Plan and manage training sessions.'], insights: ['Insights', 'Understand progress over time.'], settings: ['Settings', 'Manage your workspace preferences.'], clients: ['Clients', 'Your coaching roster.'], dashboard: ['Overview', 'Your workspace.'], 'recent-analysis': ['Form analysis', 'Your movement reviews.'] }
export default function PlaceholderPage({ activeTab, onTabChange }: { activeTab: AppTab; onTabChange: (tab: AppTab) => void; onLogout: () => void }) {
  const [title, description] = copy[activeTab]
  return <main className="page-content"><PageHeader eyebrow="Workspace" title={title} description={description} /><Card><EmptyState title={`${title} is on the way`} action={<Button variant="secondary" onClick={() => onTabChange('dashboard')}>Back to overview<ArrowRight size={16} /></Button>}>This feature is not available yet. Your current coaching tools are ready to use.</EmptyState><StatusBadge>Coming soon</StatusBadge></Card></main>
}
