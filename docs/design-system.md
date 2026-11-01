# Vectra Design System — Volt Performance Light

The current visual direction is premium light SaaS with an athletic soul. Use clean neutral surfaces, readable Inter typography, and selective lime accents. Preserve existing routes, role-aware navigation, workflows, API integrations and component APIs when extending the interface. Historical dark-theme guidance in this document is superseded by these current rules.

## Foundations and tokens

`vectra-ui/src/design-system/tokens.ts` is the platform-neutral source for palette, typography, spacing, radii, motion and shadows. `installTokens()` exposes the values as CSS custom properties. `vectra-ui/src/theme.ts` adapts the same tokens for legacy inline styles; do not create another palette there. Native apps may reuse token values, not DOM components or the web installer.

| Purpose | Token | Value |
| --- | --- | --- |
| Primary action | `--button-primary-bg` | `#172022` |
| Primary action text | `--button-primary-text` | `#FFFFFF` |
| Action hover | `--button-primary-hover` | `#293638` |
| Action pressed | `--button-primary-pressed` | `#101719` |
| Secondary action | `--button-secondary-bg` | `#FFFFFF` |
| Secondary border | `--button-secondary-border` | `#D9E1DD` |
| Tertiary hover | `--button-tertiary-hover` | `#F3F6F2` |
| Brand highlight | `--color-brand-highlight` | `#C9FF51` |
| Selected / subtle surface | `--color-brand-subtle` | `#F2F9E6` |
| Workspace background | `--color-background` | `#FAFBFC` |
| App background base | `--app-background-base` | `#FAFBFC` |
| Authenticated shell gradient | `--app-background-gradient` | `linear-gradient(135deg, #EAF6D9 0%, #F5FAEF 42%, #FAFBFC 85%)` |
| Surface / card | `--color-surface` | `#FFFFFF` |
| Navigation | `--sidebar-bg` | `#FFFFFF` |
| Selected navigation | `--sidebar-item-active-bg` | `#172022` |
| Primary text | `--color-text-primary` | `#151A20` |
| Secondary text | `--color-text-secondary` | `#667085` |
| Border | `--color-border` | `#E3E7E2` |
| Strong border | `--color-border-strong` | `#C7CEC7` |

`--app-background-base` and `--app-background-gradient` define the authenticated application canvas. `design-system/AppShell.tsx` applies the diagonal pearl lime gradient once to `.shell-content`, behind page content; the gradient does not repeat and reaches the base `#FAFBFC` color by its final stop. The app canvas uses the same base as a fallback. Keep standard cards, forms, tables, dialogs, the sidebar, and buttons on their solid existing surfaces. Standard cards use white. Navigation uses white inactive items and a rounded near-black selected item with white text and icons; there is no lime active indicator.

The shared token installer also exposes `--gradient-hero`, `--gradient-pearl`, `--gradient-surface`, `--gradient-sage`, and `--gradient-brand` for focused feature treatments. Standard primary buttons share the sidebar's near-black fill, white text and icons, solid hover/pressed colors, and no border or shadow. Secondary buttons use white with a neutral border. Tertiary buttons remain transparent and use the neutral hover surface.

Depth uses restrained shared shadows: card `0 2px 8px rgba(23, 32, 34, 0.03)`, hover `0 6px 18px rgba(23, 32, 34, 0.06)`, and elevated `0 12px 32px rgba(23, 32, 34, 0.08)`. Use dark foreground text on pale gradients and verify contrast for new pairs.

Primary buttons use the near-black component tokens so they match selected navigation. Secondary and tertiary buttons use the neutral component tokens. Keep lime accents selective for brand identity. Keep success (`#168455`), warning, danger and information colors semantic; blue is not success. Analysis cyan is `#36DCE0`; performance orange is `#FF814A`. Chart series use lime, cyan, orange and neutral tones with labels and units.

Semantic foregrounds use contrast-checked shades with subtle surfaces: success `#168455` on `#F8FCF9`, warning `#8C4C09` on `#FFF4DD`, danger `#B52B39` on `#FFF0F1`, and informational blue `#2563EB` on `#EDF5FD`. Keep labels/icons with these colors so status is never conveyed by color alone.

Inter is the application font for navigation, forms, tables, business metrics and body copy. Barlow Condensed is reserved for selected athletic headings and milestones. Use tabular numerals for metrics and financial values. Fonts are served locally from `public/fonts/` with system fallbacks.

The spacing scale remains 4, 8, 12, 16, 20, 24, 32 and 40px. Radii are 6, 10, 14 and 18px. Use the shared tokens rather than adding one-off palettes, radii or spacing scales. Standard UI motion is 150–200ms with the shared easing token; reduced-motion preferences disable transitions and animation.

## Application shell and roles

`design-system/AppShell.tsx` owns staff navigation and its responsive drawer. `components/SideNav.tsx` renders the same permission-aware menu on desktop and mobile. The role-aware shell keeps a white sidebar, dark inactive labels, muted inactive icons, a rounded near-black selected item with white content, white business surfaces, and the shared diagonal pearl lime gradient behind page content. Preserve current collapse/drawer behavior and keep the business/account controls in their existing location.

The shared foundations support different priorities: owners need clear business information and efficient administration; trainers need client context and coaching workflows; members need progress and training milestones. Do not add new capabilities or simulated data as part of visual work. Keep administrative screens predominantly light, with the global gradient behind cards rather than applied to individual content surfaces.

## Components and data visualization

`design-system/components.tsx` exports:

- `Button`: primary, secondary, tertiary and destructive variants with visible focus and disabled states.
- `PageHeader`: optional eyebrow, title, description and contextual actions.
- `Card`: neutral bordered white surface with restrained shadow.
- `StatusBadge`: neutral, success, warning, danger or information tone, always paired with a text label.
- `EmptyState` and `Skeleton`: explanatory empty and announced loading states, without fabricated metrics.
- `Dialog`: native modal or drawer with focus containment, Escape dismissal and focus restoration.

Existing complex client and analysis views retain their handlers and use the compatibility theme. `components/ProgressGallery.tsx` uses protected authenticated media for both thumbnails and enlarged views. Selected client states use the soft lime palette. Inputs keep visible boundaries and keyboard focus. Data views must use real values, units, time ranges and meaningful labels. Use compact comparisons and restrained chart decoration; do not infer a trend from one value. Pair color with labels, direction or another accessible cue.

## Athletic imagery

Use athletic photography selectively when it adds context to a workflow and approved media is available. Favor athletes performing real movements, clear subjects, natural dramatic lighting and purposeful crops. Avoid generic stock imagery, repeated unrelated photos, fabricated progress imagery and decorative hero photos across administrative pages. Images need responsive sizing, descriptive alternate text, loading behavior and a useful fallback. Use exercise media for workout content and member imagery only where the application already has it.

## Accessibility and responsive behavior

Use semantic HTML, visible labels, logical heading order, descriptive image alternatives and visible keyboard focus. Keep text and controls readable against their surfaces; never rely on color alone for status. Preserve the 44px minimum interactive target and native form behavior. Test desktop, laptop, tablet and mobile layouts, including navigation, stacked cards, tables, tab overflow, image crops and forms. Keep touch layouts usable at 320px width. Respect `prefers-reduced-motion` and avoid perpetual animation.

Computed contrast for core pairs (WCAG relative luminance):

| Pair | Contrast |
| --- | ---: |
| Primary action / charcoal label | 14.29:1 |
| Primary text / white | 17.05:1 |
| Secondary text / workspace background | 4.74:1 |
| Light text / charcoal sidebar | 17.13:1 |
| Muted light text / charcoal sidebar | 10.40:1 |
| Success / success surface | 4.54:1 |

These token-pair checks are not a formal audit of every dynamic content combination. Verify contrast when adding new foreground/background pairings.

## Examples

```tsx
<PageHeader
  eyebrow="Business / people"
  title="Business access"
  description="Manage staff in the selected workspace."
  actions={<Button onClick={openInvitation}>Invite staff</Button>}
/>
<Card>
  <StatusBadge tone="warning">Renewal grace period</StatusBadge>
  <p>Use the actual server-provided expiry date here.</p>
</Card>
```

```css
.feature-panel {
  padding: var(--space-6);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  color: var(--color-text-primary);
}
```

## Verification and extension

Run `npm run lint` and `npm run build` in `vectra-ui`. Check dashboard, client profile, workout, nutrition, form analysis and authentication at desktop and mobile widths, keyboard interactions, reduced motion, real/empty/loading states and permission-specific navigation. Use the existing design-system components and tokens for future features, including gym management and payments. Keep backend APIs, database schemas and product workflows out of visual-only changes.
