import { API_BASE_URL } from './apiConfig'
import { buildAuthHeaders } from './session'

export type GymPlan = { id: string; kind: 'gym' | 'pt'; name: string; terms: string; amount_paise: number; duration_months: number | null; sessions: number | null; active: boolean; trainer_relationship_id: number | null; trainer_name: string }
export type GymPayment = { recipient_name: string; upi_id: string; qr_asset_id: string | null }
export type GymConfig = { display_name: string; description: string; address: string; contact_phone: string; logo_id: string | null; registration_enabled: boolean; plans: GymPlan[]; payment: GymPayment }
export type GymSetup = { revision: number; configuration: GymConfig; public_id: string | null; join_url: string | null; can_edit_payment: boolean; trainers: { id: number; email: string }[]; audit: { revision: number; actor_user_id: number; created_at: string }[] }
export type PublicGym = { available: boolean; reason?: string; public_id: string; revision: number } & Omit<GymConfig, 'registration_enabled'>
export type GymPurchase = { id: string; snapshot: { pt_service_terms?: Record<string, unknown>; gym_name: string; public_id: string; member_name: string; mobile: string; plans: GymPlan[]; payment: GymPayment; terms: string }; amount_paise: number; currency: string; status: 'pending' | 'superseded' | 'awaiting_verification' | 'rejected' | 'cancelled' | 'confirmed' | 'refunded'; needs_review: boolean; created_at: string }
export class GymApiError extends Error { status: number; constructor(message: string, status: number) { super(message); this.status = status } }
export async function gymRequest<T>(path: string, options: RequestInit = {}, authenticated = true): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers: authenticated ? buildAuthHeaders(options.headers as Record<string, string> ?? {}) : options.headers })
  const data = await response.json()
  if (!response.ok) throw new GymApiError(typeof data.detail === 'string' ? data.detail : 'Unable to complete this request. Check the entered values.', response.status)
  return data as T
}
export function jsonRequest(method: string, data: unknown): RequestInit { return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } }
export const publicGymAsset = (id: string) => `${API_BASE_URL}/public/gym-assets/${id}`
export const privateGymAsset = (id: string) => `${API_BASE_URL}/gym/assets/${id}`
export const rupees = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(paise / 100)
export async function downloadRegistration(format: 'qr.png' | 'poster.pdf') {
  const response = await fetch(`${API_BASE_URL}/gym/registration/${format}`, { headers: buildAuthHeaders() })
  if (!response.ok) { const data = await response.json(); throw new Error(data.detail || 'Download unavailable.') }
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `gym-registration-${format}`; anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
