import { tokens } from '../design-system/tokens'
import { API_BASE_URL } from './apiConfig'
import { buildAuthHeaders } from './session'

export type SoftwarePlan = { code: string; name: string; business_type: 'gym' | 'coaching'; amount_paise: number; period: string; interval: number; total_count: number }
export type SoftwareSubscription = { id: string; provider_id: string | null; key_id: string | null; status: string; cancel_requested: boolean; cancel_confirmed: boolean; error_code: string | null; plan: SoftwarePlan }
export type BillingSummary = {
  access: 'pending' | 'active' | 'grace' | 'read_only' | 'legacy'
  owner: boolean; mode: 'test' | 'live'; checkout_available: boolean; business_name: string; business_type: string
  paid_through: string | null; grace_until: string | null; legacy_until: string | null
  plans?: SoftwarePlan[]; terms_version?: string; terms?: string; subscription?: SoftwareSubscription | null
  payments?: Array<{ payment_id: string; invoice_id: string; amount_paise: number; refunded_paise: number; currency: string; period_start: string; period_end: string; paid_at: string }>
}
export type CheckoutResult = { razorpay_payment_id: string; razorpay_subscription_id: string; razorpay_signature: string }

export async function billingRequest<T>(path: string, method = 'GET', body?: object): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method, headers: buildAuthHeaders({ 'Content-Type': 'application/json' }), body: body ? JSON.stringify(body) : undefined,
  })
  const result = await response.json()
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Unable to update billing. Try again.')
  return result as T
}

export function loadBilling(id: number) { return billingRequest<BillingSummary>(`/organizations/${id}/billing`) }

interface CheckoutInstance { open: () => void; on: (event: string, callback: () => void) => void }
declare global {
  interface Window { Razorpay?: new (options: Record<string, unknown>) => CheckoutInstance }
}
let scriptPromise: Promise<void> | null = null
async function loadCheckout() {
  if (window.Razorpay) return
  if (!scriptPromise) scriptPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve()
    script.onerror = () => { script.remove(); scriptPromise = null; reject(new Error('Unable to load Razorpay checkout. Your onboarding is saved.')) }
    document.head.appendChild(script)
  })
  await scriptPromise
}

export async function openSoftwareCheckout(subscription: SoftwareSubscription, name: string, onPaid: (result: CheckoutResult) => void, onDismiss: () => void, onFailed: () => void) {
  await loadCheckout()
  if (!window.Razorpay || !subscription.provider_id || !subscription.key_id) throw new Error('Checkout is not ready yet.')
  const checkout = new window.Razorpay({
    key: subscription.key_id, subscription_id: subscription.provider_id, name: 'Vectra',
    subscription_card_change: ['pending', 'halted', 'paused'].includes(subscription.status),
    description: `${name} — ${subscription.plan.name}`, handler: onPaid,
    modal: { ondismiss: onDismiss }, theme: { color: tokens.color.brand },
  })
  checkout.on('payment.failed', onFailed)
  checkout.open()
}
