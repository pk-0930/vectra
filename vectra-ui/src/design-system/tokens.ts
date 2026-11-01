/** Platform-neutral values. Web custom properties are derived from these tokens. */
export const tokens = {
  color: {
    // Volt Performance Light: selective lime accents with neutral business surfaces.
    brand: '#b9f52a', brandHover: '#a8e51d', brandHighlight: '#c9ff51', brandSubtle: '#f2f9e6',
    onBrand: '#151a20', brandText: '#405a00',
    background: '#fafbfc', surface: '#ffffff', surfaceSubtle: '#f6f8fa',
    charcoal: '#11171b', graphite: '#1c252a', sidebarHover: '#28343a', sidebarActive: '#344047',
    text: '#151a20', muted: '#667085', onDark: '#f5f6f2', mutedDark: '#c1c9c9',
    border: '#e3e7e2', borderStrong: '#c7cec7', controlBorder: '#8b958e',
    success: '#168455', successSurface: '#f8fcf9', successBorder: '#9bc8ae',
    warning: '#8c4c09', warningSurface: '#fff4dd', warningBorder: '#d7ac68',
    danger: '#b52b39', dangerSurface: '#fff0f1', dangerBorder: '#dfa1a8',
    info: '#2563eb', infoSurface: '#edf5fd', infoBorder: '#9cbfdf',
    analysis: '#36dce0', performance: '#ff814a', chartPrimary: '#c9ff35', chartSecondary: '#667085',
    overlay: 'rgba(17,23,27,0.62)',
  },
  font: { ui: "'Inter', system-ui, sans-serif", performance: "'Barlow Condensed', sans-serif" },
  space: { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40 },
  radius: { sm: 6, md: 10, lg: 14, xl: 18 },
  motion: { fast: 150, panel: 200 },
  shadow: { card: '0 2px 8px rgba(23,32,34,0.03)', cardHover: '0 6px 18px rgba(23,32,34,0.06)', elevated: '0 12px 32px rgba(23,32,34,0.08)', drawer: '0 12px 32px rgba(23,32,34,0.08)' },
  gradient: {
    appBackground: 'linear-gradient(135deg, #EAF6D9 0%, #F5FAEF 42%, #FAFBFC 85%)',
    hero: 'linear-gradient(125deg, #FFFFFF 10%, #F5FAED 65%, #EAF6D6 100%)',
    pearl: 'linear-gradient(125deg, #FFFFFF 5%, #F6F8FA 55%, #EBF0F3 100%)',
    surface: 'linear-gradient(160deg, #FFFFFF 0%, #F8FAF8 100%)',
    sage: 'linear-gradient(125deg, #F8FCEB 0%, #E9F7DA 55%, #D8EFD7 100%)',
    brand: 'linear-gradient(115deg, #C9FF51 0%, #B9F52A 55%, #A8E51D 100%)',
  },
  component: {
    sidebarBg: '#FFFFFF', sidebarItemBg: '#FFFFFF', sidebarItemText: '#172022', sidebarItemIcon: '#66727C',
    sidebarItemHover: '#F3F6F2', sidebarItemActiveBg: '#172022', sidebarItemActiveText: '#FFFFFF', sidebarItemActiveHover: '#293638',
    buttonPrimaryBg: '#172022', buttonPrimaryText: '#FFFFFF', buttonPrimaryHover: '#293638', buttonPrimaryPressed: '#101719',
    buttonSecondaryBg: '#FFFFFF', buttonSecondaryText: '#172022', buttonSecondaryBorder: '#D9E1DD', buttonSecondaryHover: '#F5F7F5',
    buttonTertiaryHover: '#F3F6F2',
  },
} as const

const cssColorNames: Record<keyof typeof tokens.color, string> = {
  brand: 'brand-primary', brandHover: 'brand-primary-hover', brandHighlight: 'brand-highlight', brandSubtle: 'brand-subtle',
  onBrand: 'on-brand', brandText: 'brand-text', background: 'background', surface: 'surface', surfaceSubtle: 'surface-subtle',
  charcoal: 'sidebar', graphite: 'sidebar-elevated', sidebarHover: 'sidebar-hover', sidebarActive: 'sidebar-active',
  text: 'text-primary', muted: 'text-secondary', onDark: 'text-on-dark', mutedDark: 'text-muted-dark',
  border: 'border', borderStrong: 'border-strong', controlBorder: 'control-border', success: 'success', successSurface: 'success-surface', successBorder: 'success-border',
  warning: 'warning', warningSurface: 'warning-surface', warningBorder: 'warning-border', danger: 'danger', dangerSurface: 'danger-surface',
  dangerBorder: 'danger-border', info: 'info', infoSurface: 'info-surface', infoBorder: 'info-border', analysis: 'chart-tertiary',
  performance: 'chart-accent', chartPrimary: 'chart-primary', chartSecondary: 'chart-secondary', overlay: 'overlay',
}

export function installTokens() {
  const root = document.documentElement
  root.style.setProperty('--app-background-base', tokens.color.background)
  root.style.setProperty('--app-background-gradient', tokens.gradient.appBackground)
  for (const [key, value] of Object.entries(tokens.color)) {
    root.style.setProperty(`--color-${key}`, value)
    root.style.setProperty(`--color-${cssColorNames[key as keyof typeof tokens.color]}`, value)
  }
  for (const [key, value] of Object.entries(tokens.space)) root.style.setProperty(`--space-${key}`, `${value}px`)
  for (const [key, value] of Object.entries(tokens.radius)) root.style.setProperty(`--radius-${key}`, `${value}px`)
  for (const [key, value] of Object.entries(tokens.font)) root.style.setProperty(`--font-${key}`, value)
  root.style.setProperty('--font-display', tokens.font.performance)
  for (const [key, value] of Object.entries(tokens.motion)) root.style.setProperty(`--motion-${key}`, `${value}ms`)
  root.style.setProperty('--motion-standard', `${tokens.motion.panel}ms`)
  for (const [key, value] of Object.entries(tokens.shadow)) root.style.setProperty(`--shadow-${key}`, value)
  for (const [key, value] of Object.entries(tokens.gradient)) root.style.setProperty(`--gradient-${key}`, value)
  const componentCssNames: Record<keyof typeof tokens.component, string> = {
    sidebarBg: 'sidebar-bg', sidebarItemBg: 'sidebar-item-bg', sidebarItemText: 'sidebar-item-text', sidebarItemIcon: 'sidebar-item-icon',
    sidebarItemHover: 'sidebar-item-hover', sidebarItemActiveBg: 'sidebar-item-active-bg', sidebarItemActiveText: 'sidebar-item-active-text', sidebarItemActiveHover: 'sidebar-item-active-hover',
    buttonPrimaryBg: 'button-primary-bg', buttonPrimaryText: 'button-primary-text', buttonPrimaryHover: 'button-primary-hover', buttonPrimaryPressed: 'button-primary-pressed',
    buttonSecondaryBg: 'button-secondary-bg', buttonSecondaryText: 'button-secondary-text', buttonSecondaryBorder: 'button-secondary-border', buttonSecondaryHover: 'button-secondary-hover', buttonTertiaryHover: 'button-tertiary-hover',
  }
  for (const [key, value] of Object.entries(tokens.component)) root.style.setProperty(`--${componentCssNames[key as keyof typeof tokens.component]}`, value)
  root.style.setProperty('--motion-ease', 'cubic-bezier(0.2, 0.8, 0.2, 1)')
}
