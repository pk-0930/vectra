# Vectra Client Portal Implementation Plan

## Summary
Build the Vectra Client Portal as a separate production-ready product inside the same repository, with its own FastAPI backend and React TypeScript frontend. Phase 1 should faithfully digitize the attached Excel workbook workflow : meal plans, workout plans, daily check-ins, weekly body measurements, and progress pictures.

The Client Portal is read-oriented for coach-created programming. Clients can activate an invited account, sign in, view assigned plans, complete daily progress tracking, add weekly measurements, upload progress pictures, and manage basic account actions.

## Engineering Principle
The Client Portal and Coach Portal are independent applications, but they should follow the same engineering conventions, coding standards, REST API style, frontend organization, authentication model, and UI design language to maintain consistency across the Vectra ecosystem.

Do not share source files between portals. Shared consistency should come from architecture and conventions, not imports.

## Functional Modules
- **Dashboard**
  - Show current meal plan, current workout plan, today’s daily check-in status, latest body measurement entry, latest progress photos, current goal, coach name, and program status.

- **Meal Plans**
  - Digitize the `Meal Planner` worksheet as structured coach-created nutrition content.
  - Preserve meal sections, options, outside options, cooked/raw measurement notes, quantities, meal preference, recipe links, and instructions.
  - Client Portal is read-only for meal plans.

- **Workout Plans**
  - Digitize the `GYM WORKOUTS` worksheet as a six-week coach-created workout program.
  - Preserve week, day, muscle group, exercise, reps, assigned weight, warm-up links, stretching links, and exercise demo links.
  - Client Portal is read-only for workout plans in V1.
  - Workout logging is postponed to a future version.

- **Daily Check-ins**
  - Digitize the `Weight & HABIT Tracker` worksheet.
  - Track one check-in per client per day:
    - weight
    - water intake
    - steps
    - meditation
    - sleep
    - walk after meals
    - skipping

- **Body Measurements**
  - Digitize the `Body Measurements` worksheet as weekly measurement history.
  - Track one entry per client per measurement date:
    - left arm
    - right arm
    - left thigh
    - right thigh
    - waist top
    - waist middle
    - waist lower

- **Progress Pictures**
  - Preserve the current design direction.
  - Support weekly front, back, and side angle uploads with captured date.
  - Do not redesign upload ownership yet; revisit after product workflow is finalized.

- **Profile**
  - Add a dedicated mostly read-only profile page.
  - Personal Information: first name, last name, date of birth, gender, height, current weight.
  - Fitness Information: coach name, current goal, program status.
  - Account: email, change password, logout.
  - Clients should not edit assigned coach, goal, height, or date of birth.

## User Journey
1. Coach creates a client and client account from the Coach Portal.
2. Client receives an invitation or activation link.
3. Client activates account using `POST /auth/activate`.
4. Client signs in using `POST /auth/signin`.
5. Client lands on Dashboard and sees current program status.
6. Client views current meal plan and historical meal plans.
7. Client views current workout plan and historical workout plans.
8. Client completes daily check-ins.
9. Client records weekly body measurements.
10. Client uploads weekly progress photos.
11. Client reviews Profile and can change password or log out.

## Frontend Architecture
- Create an independent React + TypeScript + Vite app, recommended path: `client-portal-ui/`.
- Use feature-based folders:
  - `src/features/auth/`
  - `src/features/dashboard/`
  - `src/features/mealPlans/`
  - `src/features/workoutPlans/`
  - `src/features/progress/`
  - `src/features/profile/`
  - `src/services/`
  - `src/types/`
  - `src/theme/`
  - `src/routes/`
- Use protected routes and auth bootstrap via `GET /auth/me`.
- Use an API service layer with typed request/response models.
- Use resource-oriented modules matching backend resources.
- Follow the Coach Portal’s naming conventions, TypeScript conventions, UI spacing, typography, and design language without sharing code.

## Navigation
Use the finalized navigation:

- Dashboard
- Meal Plans
- Workout Plans
- Progress
  - Daily Check-ins
  - Body Measurements
  - Progress Photos
- Profile

Remove tracker-based navigation names.

## Backend Architecture
- Create an independent FastAPI backend, recommended path: `client-portal-api/`.
- Use folders:
  - `routers/`
  - `services/`
  - `repositories/`
  - `schemas/`
  - `config/`
  - `middleware/`
  - `tests/`
- Keep HTTP handlers thin.
- Put business rules in services.
- Put database access in repositories.
- Put request/response validation in Pydantic schemas.
- Use environment-based configuration for PostgreSQL, auth secrets, CORS, and file storage.
- Maintain independent auth implementation while staying compatible with shared `users` and `clients` database design.

## Authentication
Client accounts are invitation-based. Clients do not self-register.

- Coach creates the client account.
- Client activates the invited account.
- Client signs in after activation.
- Client identity is linked through `clients.user_id -> users.id`.

Auth APIs:

- `POST /auth/activate`
  - Purpose: activate coach-created client account and set password.
  - Auth: public activation token or invitation code.
  - Request: activation token, password.
  - Response: bearer token, user, client profile.

- `POST /auth/signin`
  - Purpose: client login.
  - Auth: public.
  - Request: email, password.
  - Response: bearer token, user, client profile.

- `GET /auth/me`
  - Purpose: restore session and return current client context.
  - Auth: client bearer token.
  - Response: user and linked client profile.

## Database Design
Reuse existing shared tables:

- `users`
- `coaches`
- `clients`
- `client_goals`
- `nutrition_plans`
- `workout_plans`
- `client_progress_photos`

Update `clients`:

- Add `user_id BIGINT NULL REFERENCES users(id)`.
- Add `status TEXT NOT NULL DEFAULT 'ACTIVE'`.
- Replace `is_active` with enum-like status values:
  - `ACTIVE`
  - `PAUSED`
  - `COMPLETED`
  - `ARCHIVED`

Add `client_daily_checkins`:

- `id`
- `client_id`
- `checkin_date`
- `weight`
- `water_intake`
- `steps`
- `meditation`
- `sleep`
- `walk_after_meals`
- `skipping`
- `created_at`
- `updated_at`
- Unique constraint: one check-in per client per day.

Add `client_measurements`:

- `id`
- `client_id`
- `measured_on`
- `left_arm`
- `right_arm`
- `left_thigh`
- `right_thigh`
- `waist_top`
- `waist_middle`
- `waist_lower`
- `created_at`
- `updated_at`
- Unique constraint: one measurement entry per client per measurement date.

Do not add in V1:

- `client_user_accounts`
- `client_workout_logs`
- `client_program_assets`

Keep recipe links, exercise demo links, and plan metadata inside existing JSON plan structures.

## API Specification
- `GET /dashboard`
  - Purpose: current client overview.
  - Auth: client bearer token.
  - Response: current plans, today’s check-in status, latest measurement from history, latest progress photos, coach, goal, status.

Meal plan APIs:

- `GET /meal-plans/current`
- `GET /meal-plans/history`
- `GET /meal-plans/{plan_id}`
- `GET /meal-plans/{plan_id}/pdf`

Workout plan APIs:

- `GET /workout-plans/current`
- `GET /workout-plans/history`
- `GET /workout-plans/{plan_id}`
- `GET /workout-plans/{plan_id}/pdf`

Daily check-in APIs:

- `GET /daily-checkins?start_date=&end_date=`
- `POST /daily-checkins`
- `PUT /daily-checkins/{checkin_id}`

Measurement APIs:

- `GET /measurements`
- `POST /measurements`
- `PUT /measurements/{measurement_id}`

Progress photo APIs:

- `GET /progress-pictures`
- `POST /progress-pictures`
- `GET /progress-pictures/{photo_id}`

Profile APIs:

- `GET /profile`
- `PUT /profile/password`
- `POST /auth/logout` if server-side token invalidation is introduced; otherwise logout remains client-side token removal.

## Development Roadmap
- **Milestone 1: Planning Artifact**
  - Create `CLIENT_PORTAL_IMPLEMENTATION_PLAN.md`.
  - Include workbook analysis, architecture, APIs, database design, roadmap, risks, security, and performance notes.
  - Create branch `codex/client-portal-implementation-plan`.
  - Commit only the Markdown planning document.
  - Push branch.

- **Milestone 2: Project Scaffolding**
  - Add `client-portal-api/` and `client-portal-ui/`.
  - Add independent env examples, startup docs, Docker files if required, and validation commands.

- **Milestone 3: Client Auth And Activation**
  - Implement activation, sign-in, session restore, password hashing, JWT handling, and client context resolution.

- **Milestone 4: Read-Only Plans**
  - Implement current/history/detail/PDF APIs and UI for meal plans and workout plans.

- **Milestone 5: Progress Tracking**
  - Implement daily check-ins, body measurements, and progress photo flows.

- **Milestone 6: Profile And Polish**
  - Implement profile page, change password, error states, loading states, responsive UI, and accessibility pass.

- **Milestone 7: Production Readiness**
  - Add backend tests, frontend lint/build validation, security hardening, upload validation, indexes, and deployment configuration.

## Security Considerations
- No client self-registration.
- Activation tokens must be single-use, expiring, and scoped to one client.
- Enforce client-level authorization on every endpoint.
- A client can only access data linked to their own `clients.id`.
- Hash passwords securely.
- Store JWT secret and database credentials in environment variables.
- Restrict CORS by environment.
- Validate all inputs with Pydantic.
- Validate progress photo uploads by file type, file size, and storage path.
- Do not expose coach-only mutation APIs through the Client Portal.

## Performance Considerations
- Use date-window filtering for check-ins.
- Paginate plan history, measurement history, and progress photos as data grows.
- Add indexes on:
  - `clients.user_id`
  - `clients.status`
  - `client_daily_checkins(client_id, checkin_date)`
  - `client_measurements(client_id, measured_on)`
  - `client_progress_photos(client_id, captured_on)`
- Keep plan JSON payloads structured and avoid over-fetching where summary endpoints are enough.
- Store images in blob/file storage, not PostgreSQL.

## Risks
- Some workbook behavior may be implicit in coach workflow rather than formulas.
- Existing plan JSON structures may need standardization for clean client rendering.
- Replacing `is_active` with `status` may affect existing Coach Portal assumptions.
- Activation flow requires careful coordination with coach-created clients.
- Progress photo ownership and workflow are not finalized and should remain flexible.
- PDFs must respect existing coach-created plan content without exposing unrelated client data.

## Future Enhancements
- Workout completion logging.
- Exercise-level progress tracking.
- Client messaging or coach feedback threads.
- Push/email reminders for missed check-ins.
- Meal substitution requests.
- Progress charts and trend analytics.
- Mobile-first PWA experience.
- Coach-configurable progress photo cadence.
- AI-assisted client insights after Phase 1 workflow parity is complete.

## Test Plan
- Backend unit tests:
  - activation token success/failure
  - sign-in success/failure
  - `GET /auth/me`
  - client ownership checks
  - read-only meal plan endpoints
  - read-only workout plan endpoints
  - daily check-in create/update and uniqueness
  - measurement create/update and uniqueness
  - progress photo validation
  - profile read and password change

- API authorization tests:
  - unauthenticated requests rejected
  - client cannot access another client’s plans, check-ins, measurements, or photos
  - archived/paused/completed client status behavior is explicit and tested

- Frontend validation:
  - `npm run lint`
  - `npm run build`
  - manual route protection testing
  - responsive checks for dashboard, plan views, progress screens, and profile

- Manual workbook parity tests:
  - meal sections and options match workbook
  - six-week workout layout is faithfully represented
  - daily check-in fields match habit tracker
  - weekly measurements match workbook fields
  - progress pictures support front/back/side grouping

## Assumptions
- Phase 1 reproduces the workbook workflow and does not introduce new coaching features.
- Coach Portal remains the source of truth for creating clients and assigning plans.
- Client Portal reads coach-created meal and workout plans.
- A client account maps to exactly one client profile in Phase 1.
- Progress photo workflow remains unchanged until product finalization.
- Application implementation begins only after this plan is written, reviewed, committed, and approved.
