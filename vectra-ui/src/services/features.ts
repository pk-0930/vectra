import { API_BASE_URL } from './apiConfig'

// Loaded before rendering; the server is the single source of truth.
export const features = { formAnalysis: false }

export async function loadFeatures() {
  try {
    const response = await fetch(`${API_BASE_URL}/features`, { cache: 'no-store', signal: AbortSignal.timeout(5000) })
    if (!response.ok) return
    const configuration = await response.json()
    features.formAnalysis = configuration.form_analysis === true
  } catch {
    // Fail closed while keeping the gym workspace available.
    features.formAnalysis = false
  }
}
