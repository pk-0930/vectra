# Premium Coach UI Refresh

## Summary
Refresh the Vectra UI from a plain blue/white admin shell into a more elegant coaching workspace: richer color tokens, subtle depth, tasteful gradients, and consistent `lucide-react` icons across navigation, KPI cards, actions, tabs, empty states, and status surfaces. Keep the app professional and operational, not flashy.

## Key Changes
- Add `lucide-react` as the icon library and use it for:
  - side navigation items
  - hamburger/menu control
  - KPI tiles
  - primary/secondary action buttons where helpful
  - client workspace tabs
  - empty states and status badges
- Expand `theme.ts` into a Premium Coach palette:
  - deep navy/ink foundation
  - Vectra blue as primary
  - teal/lime accent for coaching/progress energy
  - amber/red/green status colors
  - richer surfaces, softer borders, stronger shadows
- Update shared UI styling patterns:
  - cards with subtle tinted headers or accent strips
  - buttons with icon+label treatment
  - active tabs with stronger visual contrast
  - drawers with cleaner headers and improved field grouping
  - side nav with icon-first collapsed state and full icon+label expanded state
- Apply the refresh to the current main surfaces:
  - Dashboard KPI cards and navigation blocks
  - Clients workspace, client rail, profile/nutrition/workout/form-analysis tabs
  - Recent Analysis cards and status treatments
  - Placeholder pages for visual consistency
  - Login page enough to match the new brand direction

## Public Interfaces / Types
- Add dependency: `lucide-react`.
- No backend API changes.
- No route or data model changes.
- Theme tokens may gain new keys for accents, gradients, nav states, buttons, status surfaces, and icon sizing.

## Test Plan
- Run `npm run lint`.
- Run `npm run build`.
- Manually inspect:
  - side nav collapsed/hover-expanded states
  - dashboard KPI cards
  - client list and all client workspace tabs
  - drawers and labeled fields
  - Recent Analysis cards
  - login page
- Confirm icons render, buttons remain readable, and no text overlaps in the main desktop layout.

## Assumptions
- Use the “Premium Coach” direction: polished, rich, restrained, professional.
- Use `lucide-react` for icons instead of custom inline SVGs.
- Keep the current layout and information architecture; this is a visual/design-system refresh, not a workflow redesign.
