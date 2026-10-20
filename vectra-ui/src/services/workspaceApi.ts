import { gymRequest, jsonRequest } from './gymApi'
import type { Goal } from '../types/client'
export type InboxItem = { id: number; subject: string; message: string; created_at: string; read_at: string | null }
export type Inbox = { items: InboxItem[]; unread: number; next_before: number | null }
export type Report = {
  start: string; end: string; as_of: string; purchases_enabled: boolean
  collections: { method: string; payments: number; amount_paise: number }[]
  refunds: { verified_collection: boolean; refunds: number; amount_paise: number }[]
  memberships: { active_members: number; expiring_members: number }
  pt_purchases: { status: string; purchases: number; amount_paise: number }[]
}
export const fetchInbox = (before?: number) => gymRequest<Inbox>(`/inbox${before ? `?before=${before}` : ''}`)
export const readInboxItem = (id: number) => gymRequest(`/inbox/${id}/read`, { method: 'POST' })
export const sendAnnouncement = (data: { request_id: string; audience: string; subject: string; message: string }) => gymRequest<{ recipient_count: number }>('/organization/announcements', jsonRequest('POST', data))
export const fetchReport = (start: string, end: string) => gymRequest<Report>(`/organization/reports?start=${start}&end=${end}`)
export const setPurchasesEnabled = (enabled: boolean) => gymRequest('/organization/web-rollout', jsonRequest('PUT', { purchases_enabled: enabled }))
export const fetchCoachingAccess = (id: number) => gymRequest<{ can_upload: boolean; historical_access: boolean }>(`/clients/${id}/coaching-access`)
export const fetchGoals = (id: number) => gymRequest<Goal[]>(`/clients/${id}/goals`)
