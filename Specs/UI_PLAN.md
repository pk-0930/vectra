# System-Wide UI Redesign with KPI Dashboard, Client-Specific Form Analysis, and Separate Nutrition/Workout Tabs

## Summary
Redesign the frontend into a calmer, guided coach workspace with a **true KPI dashboard** and a **client-owned workflow model**. The dashboard becomes a KPI/navigation surface only. Operational work moves into the client workspace, where major domains are separated into distinct tabs so the UI feels lighter and more obvious.

The target client workspace becomes:
- `Profile`
- `Nutrition`
- `Workout`
- `Form Analysis`

This keeps nutrition and workout planning clearly separate while also moving form analysis fully into client context.

## Key Changes

### 1) Reframe information architecture
- Keep the app-level left sidebar for primary navigation.
- Redefine page responsibilities:
  - `Dashboard`: coach operations KPIs and navigation only
  - `Clients`: full client workspace
  - `Recent Analysis`: optional cross-client library, secondary to client-owned analysis
- Update the selected-client workspace tabs to:
  - `Profile`
  - `Nutrition`
  - `Workout`
  - `Form Analysis`
- Remove the combined `Plans` tab concept.

### 2) Redesign `Dashboard` as a KPI page
- Remove form-analysis upload and review UI from `Dashboard`.
- Replace it with summary cards and navigation blocks only.
- First-release KPI content should include:
  - total clients
  - active clients
  - clients with current goals
  - recent form analyses count/status snapshot
  - recent plan activity snapshot
- Add lightweight jump-off actions only:
  - open client workspace
  - review recent analyses
  - create client
- Do not place large forms, uploads, or dense result panels on the dashboard.

### 3) Keep nutrition and workout fully separate
- Add a dedicated `Nutrition` tab for:
  - nutrition plan history
  - nutrition plan create/edit flow
  - nutrition PDF export
- Add a dedicated `Workout` tab for:
  - workout plan history
  - workout plan create/edit flow
  - workout PDF export
- Each tab should have its own:
  - summary header
  - latest plan snapshot
  - history list
  - primary CTA
  - creation/edit drawer
- Do not mix nutrition and workout forms or histories in the same visible surface.

### 4) Move form analysis into a dedicated client tab
- Add a `Form Analysis` tab inside the selected client workspace.
- The tab owns the full client-specific workflow:
  - upload squat video for the selected client
  - show current queued/running/completed/failed analyses
  - open and review a selected analysis
  - save coach feedback note
  - export PDF
- Review layout should be progressive:
  - analysis summary
  - frame/rep inspection
  - corrective recommendations
  - coach note + export actions
- Use existing client-scoped form-analysis endpoints.

### 5) Simplify the `Profile` tab
- Keep `Profile` focused on client identity and progress:
  - summary card
  - read-first profile details
  - edit profile drawer
  - update goal drawer
  - progress-photo timeline
  - add progress photo drawer
- Remove planning and analysis responsibilities from `Profile`.

### 6) Stronger form usability standards
- Every field must have a visible persistent label.
- Date fields must always have labels above them.
- File inputs must show:
  - field label
  - helper text
  - selected file state if applicable
- Group inputs under clear section headers.
- Use drawers for complex create/edit tasks:
  - create client
  - edit profile
  - update goal
  - add progress photo
  - create nutrition plan
  - create workout plan

### 7) Shared design system updates
- Expand the current theme/token module into reusable tokens for:
  - color
  - spacing
  - typography
  - radii
  - shadows
  - field states
  - cards
  - tabs
  - KPI tiles
  - drawers
- Add reusable UI primitives for:
  - page shell
  - KPI card
  - section header
  - labeled field
  - helper/error text
  - drawer
  - empty state
  - timeline card
  - history list row/card
- Replace page-local duplicated style patterns where practical.

## Public Interfaces / Types
- No backend API redesign is required.
- Frontend client workspace tab types should change from:
  - `profile | plans | analysis-history`
  to:
  - `profile | nutrition | workout | form-analysis`
- Existing nutrition, workout, progress-photo, and client-scoped form-analysis APIs remain the source of truth.
- Frontend view-model helpers may be added for:
  - dashboard KPI aggregation
  - nutrition tab display models
  - workout tab display models
  - form-analysis display models

## Test Plan
- Verify `Dashboard` contains KPI summaries and navigation only; no upload/review UI remains there.
- Verify `Clients` workspace contains `Profile`, `Nutrition`, `Workout`, and `Form Analysis`.
- Verify `Nutrition` tab works end-to-end:
  - create plan
  - view history
  - export PDF
- Verify `Workout` tab works end-to-end:
  - create plan
  - view history
  - export PDF
- Verify `Form Analysis` works end-to-end:
  - upload video
  - queued/running/completed states
  - review result
  - save coach note
  - export PDF
- Verify `Profile` still supports profile edits, goal updates, and progress-photo timeline management.
- Verify every input across auth, client profile, progress photos, nutrition, workout, and form analysis has a visible label.
- Verify empty states for:
  - no client selected
  - no nutrition plans
  - no workout plans
  - no form analyses
  - no progress photos

## Assumptions
- Nutrition and workout should be treated as distinct coaching workflows, not a combined planning surface.
- Dashboard remains KPI/navigation-only.
- Client-specific form analysis is the primary analysis workflow.
- `Recent Analysis` remains as a cross-client library, secondary to the client tab.
- The redesign is desktop-first and keeps the current sidebar shell.
- Drawers are preferred over long inline forms and over full navigation away for create/edit tasks.
