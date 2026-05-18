# Elegant Palette Rebalance: Slate + Electric Blue

## Summary
Rebalance the Premium Coach refresh into a sportier, cleaner visual system. The final direction uses slate/navy structure with electric-blue active states, primary actions, and focused highlights. It removes the earlier blue-green and champagne-heavy treatments while keeping the richer icon-based UI.

## Key Changes
- Keep `lucide-react` icons across navigation, KPI cards, actions, tabs, empty states, and status surfaces.
- Use a restrained Slate + Electric Blue palette:
  - slate/navy for structure and app chrome
  - electric blue for primary actions and active states
  - ice-blue muted surfaces for selected cards and icon badges
  - semantic green/amber/red only for status meaning
- Keep gradients rare:
  - subtle app background
  - dark nav/brand depth
  - restrained login brand mark
- Avoid repeated multi-color gradients on:
  - primary buttons
  - active tabs
  - PDF/action chips
  - KPI and panel icon badges

## Current UI Architecture
- `Dashboard` is KPI/navigation-only.
- `Clients` owns the main operational workspace:
  - `Profile`
  - `Nutrition`
  - `Workout`
  - `Form Analysis`
- `Recent Analysis` remains a secondary cross-client library.
- Side navigation is collapsed by default, expands on hover, and keeps icon-first navigation.
- Complex create/edit workflows use drawers.
- Form fields keep persistent visible labels.

## Public Interfaces / Types
- No backend API changes.
- No route or data model changes.
- `lucide-react` remains the frontend icon dependency.
- Shared UI tokens live in `vectra-ui/src/theme.ts`.

## Test Plan
- Run `npm run lint`.
- Run `npm run build`.
- Manually inspect:
  - side nav collapsed and hover-expanded states
  - dashboard KPI cards and navigation blocks
  - client rail, workspace tabs, drawers, and form-analysis workflow
  - recent analysis cards and selected state
  - login page brand mark and submit button

## Assumptions
- The product should feel sporty, technical, and elegant.
- Electric blue is the only brand accent; green is reserved for success states.
- Existing workflows and layout remain unchanged.
