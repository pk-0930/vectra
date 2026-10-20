const TOKEN_STORAGE_KEY = 'vectra.accessToken'
let businessId: number | null = null
let generation = 0
let accessMode = 'staff'

export function getStoredAccessToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY) ?? ''
}

export function setStoredAccessToken(token: string) {
  generation++
  businessId = null
  for (const key of ['vectra.activeTab', 'vectra.selectedClientId']) window.localStorage.removeItem(key)
  if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
  else window.localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export function selectBusiness(id: number | null) {
  for (const key of ['vectra.activeTab', 'vectra.selectedClientId']) window.localStorage.removeItem(key)
  businessId = id
  accessMode = 'staff'
  generation++
}

export function selectAccessMode(mode: 'staff' | 'member') { accessMode = mode; generation++ }

export function sessionGeneration() { return generation }

export function buildAuthHeaders(headers: HeadersInit = {}) {
  const result = new Headers(headers)
  result.set('X-Access-Mode', accessMode)
  const token = getStoredAccessToken()
  if (token) result.set('Authorization', `Bearer ${token}`)
  if (businessId !== null) result.set('X-Organization-ID', String(businessId))
  return result
}
