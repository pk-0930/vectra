# Vectra Performance OS

The application uses the Volt Performance design from `Specs/UI_VOLT_LIME.MD`. The user authorized the complete application rollout, including replacing the earlier blue theme. This is a presentation refactor: gym-management features, backend APIs, tenancy, billing policy and data contracts remain unchanged.

## Foundations

`vectra-ui/src/design-system/tokens.ts` is the source of truth for palette, typography families, spacing, radii, motion and shadows. Values are platform-neutral. `installTokens()` installs the web CSS properties once at startup. `theme.ts` adapts these same values for existing inline React styles; do not maintain a second palette there. Native apps may reuse token values, not DOM components or the installer.

- Brand: volt `#C9FF35`; charcoal `#11171B`; graphite `#1C252A`.
- Work surfaces: off-white background, white cards and neutral separators.
- Brand controls: lime fill with charcoal text. Use the dark `brandText` token for text on light surfaces. Never use bright lime text on white.
- Semantic status: dedicated success, warning, danger and information foreground/background pairs. A lime action or selected state does not mean success.
- Analysis: cyan accents on suitable dark surfaces, or the darker information token for legible text/icons on light surfaces. Orange is reserved for future meaningful performance emphasis.
- Inter handles UI, financial information and dense data. Barlow Condensed is limited to selected athletic headings. Numerals use tabular spacing where comparison matters.
- Spacing: 4, 8, 12, 16, 20, 24, 32 and 40px. Radii: 6, 10, 14 and 18px. Use the tokens instead of introducing arbitrary palettes or spacing scales.
- Fonts are served locally from `public/fonts/` with swap behavior and system fallbacks. Inter's Latin variable font and two Barlow weights total approximately 93 KB uncompressed. License files are included. Other scripts/glyphs use system fallback fonts.

## Components and layouts

`design-system/components.tsx` exports:

- `Button`: primary, secondary, tertiary, danger; standard 44px minimum height, disabled states and keyboard focus.
- `PageHeader`: optional eyebrow, title, description and contextual actions.
- `Card`: neutral bordered surface.
- `StatusBadge`: neutral, success, warning, danger or info, always with a visible textual label.
- `EmptyState`: explanation and an optional working next action.
- `Skeleton`: announced loading state with no fabricated metrics.
- `Dialog`: standard or drawer, native modal isolation, explicit Tab wrapping, Escape handling, close button, scroll containment and focus restoration.

`design-system/AppShell.tsx` owns the staff workspace navigation. `components/SideNav.tsx` renders the same permission-aware menu on desktop and in the mobile drawer. The business/account bar remains outside it so pending billing and identity states retain appropriate entry points. Billing, member and identity pages use the same tokens and controls without displaying unauthorized staff navigation.

`components/ProgressGallery.tsx` renders dated check-in thumbnails and an enlarged dialog view. It uses `ProtectedImage` for both sizes: authenticated retrieval, no public URL fallback, abort handling and object-URL cleanup remain intact.

Existing complex client/analysis renderers retain their handlers and use the compatibility theme. Responsive layout classes replace fixed grid assumptions. Do not introduce a new chart, date-picker or component dependency merely to fill the planned taxonomy. Build future components only when an implemented workflow requires them.

### Examples

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
<Dialog open={editing} title="Edit profile" onClose={closeEditor} drawer>
  {/* Existing form, validation, loading and submit handlers */}
</Dialog>
```

```css
.feature-panel {
  padding: var(--space-6);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  color: var(--color-text);
}
```

## Interaction and accessibility

Use real buttons for actions and links for navigation/downloads. Do not nest interactive elements inside a button or a clickable role-button container. Client section selectors are navigation buttons with `aria-pressed`; they do not claim ARIA tab semantics without implementing the corresponding keyboard pattern.

Label form fields visibly, preserve native autocomplete and input validation, and render request errors inside the active modal as well as the page when appropriate. Disabled/loading actions retain explanatory text. Destructive actions use danger styling; staff-role removal and subscription cancellation show contextual confirmation dialogs.

Use visible keyboard focus, maintain modal focus containment and return focus to the trigger when it still exists. Mobile navigation moves focus to the workspace when selecting a new page. The skip link targets the workspace. `prefers-reduced-motion` disables transitions/animation. No perpetual animation is used.

Computed contrast for the main token pairs:

| Pair | Ratio |
| --- | ---: |
| Main text / white | 17.49:1 |
| Muted text / off-white | 5.43:1 |
| Brand text / white | 7.63:1 |
| Charcoal text / lime | 15.35:1 |
| White text / charcoal | 17.24:1 |
| Muted dark text / charcoal | 8.92:1 |
| Success / success surface | 5.81:1 |
| Warning / warning surface | 6.10:1 |
| Danger / danger surface | 5.63:1 |
| Information / information surface | 5.21:1 |
| Control border / off-white | 3.04:1 |

These checks cover the defined pairs, not a formal accessibility certification of every possible content combination. Keep status text/icons alongside colors. Decorative card borders are intentionally subtle; interactive controls use the stronger border token.

## Responsive behavior

- Desktop sidebar: 248px, sticky, no hover-triggered layout shift.
- Below 1024px: modal navigation drawer with a visible menu control.
- Four overview metrics on wide desktops; two below 1200px; one on the narrowest screens.
- Client rail and workspace stack below 768px. The rail has its own bounded scroll region.
- Dense analysis and profile pairs collapse when the workspace is narrow.
- Tables scroll inside focusable, labeled regions. The page itself must not overflow horizontally.
- Main actions wrap, titles and filenames wrap, and native form controls remain usable on phones.
- Mobile inputs use 16px text. Use fluid widths and `minmax(0, 1fr)` for content grids.

## Role and data rules

Owners/admins have integrated business and coaching navigation. Trainers do not gain owner financial or business-access controls. People retain one account with business-scoped permissions; the workspace selector is shown only when there are multiple businesses. Member mode preserves its existing access-mode headers and the return-to-staff action.

The overview shows API-backed client counts and a clearly bounded recent-analysis sample (latest 12). Loading or failed requests do not appear as successful zero-value metrics. No attendance, revenue, streaks, biomechanical scores or trend charts are invented. Sessions and insights remain honest coming-soon screens. Future chart work needs actual series, units, time ranges, baselines and a text/table alternative.

Billing displays server access states and verified history. Browser checkout never grants entitlement. Pending, grace, read-only, legacy, cancellation and recovery behavior is unchanged. Existing client, plan, upload, protected-download, analysis, invitation and authentication handlers remain the source of behavior.

## Verification and extension

Run `npm run lint` and `npm run build` in `vectra-ui`. Check desktop, tablet and phone layouts with both populated and empty states. Verify keyboard entry/exit, error feedback, protected assets and permission-specific navigation. Use isolated fixtures for design verification; never add demo records or synthetic metrics to functional application code.

Before introducing a new UI pattern, reuse the components/tokens above and document any justified extension here. See `Specs/UI_VOLT_IMPLEMENTATION_REVIEW.md` for the completed rollout and verification boundary.
