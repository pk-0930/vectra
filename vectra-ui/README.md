# Vectra UI

React + TypeScript + Vite frontend for the Vectra coach workspace.

## Product Shape

- `Dashboard`: KPI summaries and navigation shortcuts only.
- `Clients`: primary workspace for client-owned workflows:
  - `Profile`
  - `Nutrition`
  - `Workout`
  - `Form Analysis`
- `Recent Analysis`: cross-client analysis library that reopens jobs in the client workspace.

## UI System

- Shared tokens: `src/theme.ts`
- Shared hover-expanding side nav: `src/components/SideNav.tsx`
- Icons: `lucide-react`
- Current palette: Slate + Electric Blue
  - slate/navy for structure
  - electric blue for primary actions and active states
  - ice-blue muted surfaces for selected cards and icon badges
  - minimal gradients for page/nav/brand depth only

## Development

```bash
npm install
npm run dev
```

## Verification

```bash
npm run lint
npm run build
```
