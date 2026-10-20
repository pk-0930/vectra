/** Platform-neutral values. Web custom properties are derived from these tokens. */
export const tokens = {
  color: {
    brand: '#c9ff35', brandHover: '#b8ed21', onBrand: '#11171b', brandText: '#405c08', brandSubtle: '#f0f7dc',
    background: '#f5f6f2', surface: '#ffffff', surfaceSubtle: '#f0f2ee',
    charcoal: '#11171b', graphite: '#1c252a', sidebarHover: '#263037', sidebarActive: '#263329',
    text: '#151a20', muted: '#596579', onDark: '#f8faf9', mutedDark: '#adb8bd',
    border: '#e3e7e2', controlBorder: '#849183',
    success: '#126c45', successSurface: '#eaf6ef', successBorder: '#9bc8ae',
    warning: '#8c4c09', warningSurface: '#fff4dd', warningBorder: '#d7ac68',
    danger: '#b52b39', dangerSurface: '#fff0f1', dangerBorder: '#dfa1a8',
    info: '#1668b3', infoSurface: '#edf5fd', infoBorder: '#9cbfdf',
    analysis: '#36dce0', performance: '#ff814a', overlay: 'rgba(17,23,27,0.55)',
  },
  font: { ui: "'Inter', system-ui, sans-serif", performance: "'Barlow Condensed', 'Arial Narrow', sans-serif" },
  space: { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40 },
  radius: { sm: 6, md: 10, lg: 14, xl: 18 },
  motion: { fast: 150, panel: 200 },
  shadow: { card: '0 2px 8px rgba(17,23,27,0.035)', drawer: '0 24px 60px rgba(17,23,27,0.2)' },
} as const

export function installTokens() {
  const root = document.documentElement
  for (const [key, value] of Object.entries(tokens.color)) root.style.setProperty(`--color-${key}`, value)
  for (const [key, value] of Object.entries(tokens.space)) root.style.setProperty(`--space-${key}`, `${value}px`)
  for (const [key, value] of Object.entries(tokens.radius)) root.style.setProperty(`--radius-${key}`, `${value}px`)
  for (const [key, value] of Object.entries(tokens.font)) root.style.setProperty(`--font-${key}`, value)
  for (const [key, value] of Object.entries(tokens.motion)) root.style.setProperty(`--motion-${key}`, `${value}ms`)
  for (const [key, value] of Object.entries(tokens.shadow)) root.style.setProperty(`--shadow-${key}`, value)
}
