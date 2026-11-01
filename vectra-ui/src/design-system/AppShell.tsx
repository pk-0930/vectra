import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Menu } from 'lucide-react'
import SideNav from '../components/SideNav'
import type { AppTab } from '../types/navigation'
import { Button, Dialog } from './components'
type BusinessOption = { organization_id: number; name: string }
export default function AppShell({ activeTab, onTabChange, memberAction, onSignOut, businesses, selectedBusiness, onBusinessChange, children }: { activeTab: AppTab; onTabChange: (tab: AppTab) => void; memberAction?: () => void; onSignOut?: () => void; businesses?: BusinessOption[]; selectedBusiness?: number | null; onBusinessChange?: (id: number) => void; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const content = useRef<HTMLDivElement>(null)
  const previousTab = useRef(activeTab)
  useEffect(() => {
    if (previousTab.current !== activeTab) { content.current?.focus(); previousTab.current = activeTab }
  }, [activeTab])
  const change = (tab: AppTab) => { setOpen(false); onTabChange(tab) }
  return <div className="app-shell">
    <div className="desktop-nav"><SideNav activeTab={activeTab} onTabChange={change} memberAction={memberAction} onSignOut={onSignOut} businesses={businesses} selectedBusiness={selectedBusiness} onBusinessChange={onBusinessChange} /></div>
    <div className="shell-content" id="workspace" tabIndex={-1} ref={content}>
      <div className="mobile-nav-bar"><Button variant="secondary" onClick={() => setOpen(true)} aria-label="Open navigation" aria-haspopup="dialog"><Menu size={18} /> Workspace menu</Button></div>
      {children}
    </div>
    <Dialog open={open} title="Workspace navigation" onClose={() => setOpen(false)} drawer><SideNav activeTab={activeTab} onTabChange={change} memberAction={memberAction ? () => { setOpen(false); memberAction() } : undefined} onSignOut={onSignOut ? () => { setOpen(false); onSignOut() } : undefined} businesses={businesses} selectedBusiness={selectedBusiness} onBusinessChange={onBusinessChange} /></Dialog>
  </div>
}
