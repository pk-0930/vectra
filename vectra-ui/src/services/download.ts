import { buildAuthHeaders, sessionGeneration } from './session'

export async function downloadProtected(url: string) {
  const generation = sessionGeneration()
  const response = await fetch(url, { headers: buildAuthHeaders(), cache: 'no-store' })
  if (!response.ok) throw new Error('Download unavailable. Your access may have changed.')
  const blob = await response.blob()
  if (generation !== sessionGeneration()) return
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = 'vectra-report.pdf'
  link.click()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}
