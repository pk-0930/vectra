import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Menu } from 'lucide-react'
import SideNav from '../components/SideNav'
import type { AppTab } from '../types/navigation'
import { Button, Dialog } from './components'
export default function AppShell({ activeTab, onTabChange, memberAction, children }: { activeTab: AppTab; onTabChange: (tab: AppTab) => void; memberAction?: () => void; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const content = useRef<HTMLDivElement>(null)
  const previousTab = useRef(activeTab)
  useEffect(() => {
    if (previousTab.current !== activeTab) { content.current?.focus(); previousTab.current = activeTab }
  }, [activeTab])
  const change = (tab: AppTab) => { setOpen(false); onTabChange(tab) }
  return <div className="app-shell">
    <div className="desktop-nav"><SideNav activeTab={activeTab} onTabChange={change} memberAction={memberAction} /></div>
    <div className="shell-content" id="workspace" tabIndex={-1} ref={content}>
      <div className="mobile-nav-bar"><Button variant="secondary" onClick={() => setOpen(true)} aria-label="Open navigation" aria-haspopup="dialog"><Menu size={18} /> Workspace menu</Button></div>
      {children}
    </div>
    <Dialog open={open} title="Workspace navigation" onClose={() => setOpen(false)} drawer><SideNav activeTab={activeTab} onTabChange={change} memberAction={memberAction ? () => { setOpen(false); memberAction() } : undefined} /></Dialog>
  </div>
}
