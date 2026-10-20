import { useEffect, useId, useRef } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { ArrowUpRight, X } from 'lucide-react'

export function Button({ variant = 'primary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'tertiary' | 'danger' }) {
  return <button type="button" className={`button button--${variant} ${className}`} {...props} />
}
export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{actions && <div className="header-actions">{actions}</div>}</header>
}
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`workspace-card ${className}`}>{children}</section>
}
export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info' }) {
  return <span className={`status-badge status-badge--${tone}`}>{children}</span>
}
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-mark" aria-hidden="true"><ArrowUpRight size={24} /></span><h3>{title}</h3>{children && <p>{children}</p>}{action}</div>
}
export function Skeleton({ label = 'Loading…' }: { label?: string }) {
  return <div className="skeleton" role="status"><span>{label}</span><div /><div /><div /></div>
}
/** Native modal owns focus trapping, Escape dismissal and background inertness. */
export function Dialog({ open, title, onClose, children, drawer = false }: { open: boolean; title: string; onClose: () => void; children: ReactNode; drawer?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    const dialog = ref.current!
    if (!open) return
    const trigger = document.activeElement as HTMLElement | null
    dialog.showModal()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { dialog.close(); document.body.style.overflow = previous; trigger?.focus() }
  }, [open])
  return <dialog ref={ref} className={drawer ? 'dialog dialog--drawer' : 'dialog'} aria-labelledby={id} onKeyDown={event => {
      if (event.key !== 'Tab') return
      const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]')].filter(element => element.getClientRects().length > 0)
      const first = controls[0], last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }} onCancel={event => { event.preventDefault(); onClose() }}>
    <div className="dialog-header"><h2 id={id}>{title}</h2><Button variant="secondary" className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={20} /></Button></div>
    {open && children}
  </dialog>
}
