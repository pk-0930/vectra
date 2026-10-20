import { tokens } from './design-system/tokens'
const c = tokens.color
/** Compatibility adapter for existing presentation styles; tokens remain the source of truth. */
export const THEME = {
  colors: {
    primary: c.brand, primaryDeep: c.brandText, primaryMuted: c.brandSubtle,
    indigo: c.brand, indigoMuted: c.brandSubtle, accent: c.brand, accentDeep: c.brandText,
    accentMuted: c.brandSubtle, energy: c.analysis, energyMuted: c.infoSurface,
    ink: c.text, navy: c.charcoal, ivory: c.background, surface: c.surface,
    surfaceElevated: c.surface, surfaceMuted: c.surfaceSubtle, appBackground: c.background,
    border: c.border, borderStrong: c.controlBorder, text: c.text, textMuted: c.muted,
    textSoft: c.muted, success: c.success, successSurface: c.successSurface,
    warning: c.warning, warningSurface: c.warningSurface, danger: c.danger,
    dangerSurface: c.dangerSurface, white: c.surface, onBrand: c.onBrand, onDark: c.onDark,
    mutedDark: c.mutedDark, info: c.info, infoSurface: c.infoSurface, overlay: c.overlay,
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24, page: 24 },
  typography: { pageTitle: 32, sectionTitle: 20, body: 14, caption: 12 },
  radii: { ...tokens.radius, panel: tokens.radius.lg, pill: 999 },
  shadows: { primarySoft: 'transparent', card: tokens.shadow.card, cardHover: tokens.shadow.card, drawer: tokens.shadow.drawer },
  gradients: { app: c.background, primary: c.charcoal, navy: c.charcoal, card: c.brandSubtle },
  fields: { height: 44 }, icons: { sm: 16, md: 18, lg: 22 },
}
export const PRIMARY_BORDER = `1px solid ${c.controlBorder}`
