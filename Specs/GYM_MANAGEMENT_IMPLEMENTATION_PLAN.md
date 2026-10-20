# Vectra gym management implementation plan

Status: Steps 0–8 are implemented locally; see [the web implementation report](GYM_MANAGEMENT_WEB_COMPLETION_REVIEW.md). Step 9 is deferred entirely. Step 10 web release tooling and local rehearsal are implemented, but live staging/provider verification, a real-user pilot and production rollout remain outstanding; see [the web release runbook](WEB_RELEASE_RUNBOOK.md).

This plan extends the existing coaching application to independent gyms and online coaching businesses in India. The 2026-10-20 instruction authorizes the remaining web implementation without interim reviews and defers all mobile work. Continue to distinguish implemented behavior, local verification and live release evidence.

Current release scope: form/movement analysis is deferred alongside mobile. `FORM_ANALYSIS_ENABLED` defaults to `false` and controls API access, web visibility/data requests and analysis queue processing. Historical data is preserved. Workout/nutrition plans, goals and progress photos remain available. This supersedes analysis-related delivery requirements elsewhere in this plan; see the web release runbook for configuration.

## Agreed product scope

| Area | Requirement |
| --- | --- |
| Businesses | Multiple independent gyms and independent online coaching businesses. Keep their data separate. |
| Identity | One personal account with roles in one or more businesses. Membership is separate from staff roles. |
| Owner and admin | An integrated interface with all capabilities within their business, including coaching their own clients. No owner/PT view switch. |
| PT | Invited by an admin; manages assigned clients and appointments. Removal or inactivity immediately revokes that business's PT permissions, including existing sessions. Other business/member access remains independent. |
| Member | Joins through gym onboarding, buys membership, optionally purchases PT, and accesses their own plans and progress. |
| Gym packages | Fixed purchases for 1, 3, 6, or 12 months, manually renewed. |
| PT packages | Per session or fixed purchases for 1, 3, 6, or 12 months. Admin sets prices per trainer. |
| Purchased terms | Preserve the price and terms at purchase even after catalogue edits. |
| PT eligibility | A gym PT package must fit within paid membership coverage. Disable ineligible packages, show expiry, and explain renewal requirements. |
| PT capacity | Initial limit of 10 active clients per PT. Exact counting and pending-purchase rules are a decision gate below. |
| Gym collections | Gym/owner's existing UPI QR and cash. Admin verifies actual receipt and uses a combined confirm-payment-and-activate action. |
| Software billing | Separate gym and online-coach software pricing, paid to Vectra through Razorpay with recurring authorization. Activate paid access after the first actual subscription payment is verified. |
| Online coaching | Retain existing coaching functionality; online clients do not require gym memberships. |
| Public onboarding | Permanent gym registration link and printable QR leading to the same mobile-friendly page. Registration must not require app installation. |
| Applications | Shared React web portal now, including phone browsers. React Native Android/iOS is deferred to future iterations. |
| Notifications | Persistent web inbox now. Admin can target PTs, members, and coaching clients within the business. All mobile push is deferred; browser push is outside this release. |
| Email | Azure Communication Services Email: verification/recovery as appropriate, staff invitations, membership/PT purchase confirmations, membership expiry reminders, software subscription confirmations and owner billing notices. |
| Design | Volt lime/charcoal design system, subsequently authorized and implemented across the application. See `UI_VOLT_IMPLEMENTATION_REVIEW.md` and `../docs/design-system.md`. |

The registration QR opens Vectra onboarding. The payment QR sends money to the gym/owner. Clearly distinguish them in the portal and printed materials. An uploaded payment QR does not give Vectra bank visibility or automatic verification.

### Agreed visual palette

- Volt lime `#c9ff35`: primary actions with dark text; accessible dark lime `#405c08` for text on light surfaces.
- Charcoal `#11171b` and graphite `#1c252a`: dark surfaces and navigation.
- Off-white `#f5f6f2`: workspace backgrounds; white content cards.
- Apply the same visual language across web, Android and iOS, adapting navigation to each platform.
- Use accents selectively, with strong headings, crisp icons, restrained borders and minimal glow. Keep information-heavy screens readable.
- Reserve green, amber and red for semantic statuses, paired with text/icons. Final component states must pass contrast checks.

The subsequent whole-application Volt implementation request supersedes the temporary blue restoration. Shared tokens in `vectra-ui/src/design-system/tokens.ts` are authoritative. Historical review documents describe their review-date palette.

## Current repository baseline

- `vectra-ui/` contains React, TypeScript and Vite. `src/App.tsx` handles coach signup/login and navigation; sessions, insights and settings currently use placeholder pages.
- `mobility-ai-service/` contains FastAPI, services, repository adapters and an analysis queue worker. Existing features include clients, goals, progress photos, nutrition/workout plans, AI plan drafts, PDFs and form analysis.
- `services/auth_service.py` creates coach profiles. `app.py:get_current_user` requires a coach profile, so it cannot yet serve general members/admins independently.
- `database/migrations/V1__baseline.sql` has global users, coach profiles and coach-owned clients. `associated_gym` is profile text, not an isolated gym entity. V2 backfills legacy jobs.
- The frontend has lint/build scripts and no configured test runner. Backend tests use unittest. No React Native application was identified in this inspection.
- These are local code observations, not confirmation of live Azure schema, credentials, deployed services or production readiness.

Earlier WhatsApp-first planning is separate planned work. The new requirements establish individual logins and multiple businesses; do not import the older one-coach/no-client-login assumptions or add WhatsApp integration to this release without a separate decision.

## Working method

1. Implement the remaining web scope under the 2026-10-20 authorization; do not stop for interim reviews. Document reasonable product defaults and external release blockers.
2. Recheck repository state and applicable instructions; keep changes in a focused PR or reviewable diff.
3. Implement the smallest complete behavior with migration/configuration notes where relevant.
4. Run the step's checks and required application checks. Demonstrate the behavior, including failures and permissions.
5. Report completed work, remaining limitations and rollout/rollback instructions. Do not represent unavailable live-provider or pilot evidence as passed.

Use mocks for unavailable providers during development. A mock passing is not evidence that live payment, email or push works. Credentials can be added later, but real provider verification is mandatory before releasing the dependent feature.

## Delivery sequence

| Step | Deliverable | Depends on |
| --- | --- | --- |
| 0 | Reviewed business rules, permission matrix and representative screen designs | This plan |
| 1 | Organization model and safe migration of existing coaching records | 0 |
| 2 | General accounts, tenant permissions and integrated web shell | 1 |
| 3 | Email delivery, verification/recovery and staff invitations | 2 |
| 4 | Paid business onboarding and Vectra Razorpay subscriptions | 3 |
| 5 | Gym catalogue, public registration and QR downloads | 4 |
| 6 | Manual UPI/cash verification and membership lifecycle | 5 |
| 7 | PT purchases, assignments, capacity and appointments | 6 |
| 8 | Member coaching access, owner reporting and notification inbox | 7 |
| 9 | React Native application and push delivery — deferred | Future iteration |
| 10 | Web staging rehearsal, pilot and production release | 8; no mobile dependency |

Current delivery order: Steps 0–7 → Step 8 → web-only Step 10. Step 9 and every native-app/push check remain future work. Responsive web verification remains in scope.

### Step 0 — Resolve rules and review designs

Deliver a permission matrix, core entity diagram, API outline and representative designs for owner dashboard, trainer client list, member home and QR onboarding. Document shared typography, colors, spacing, forms, states and accessible contrast for web and mobile. The owner has one integrated navigation; a business selector appears only when needed for multiple business relationships.

Decisions to resolve before their dependent work:

| Decision | Proposed direction to review | Required by |
| --- | --- | --- |
| Authentication | Verified email/password initially; decide whether member phone login is needed. ACS Email does not provide SMS OTP by itself. | 2–3 |
| Owner versus admin | Shared daily operations; define who may add admins, change payment destinations and transfer ownership. Protect the last owner. | 2 |
| Legacy businesses | Map existing coaches to independent coaching businesses; define subscription transition/grandfathering without suddenly locking them out. | 1, 4 |
| Software plans | Actual prices, billing intervals, cancellation timing, grace period, reactivation, refunds and restricted-access behavior when unpaid. | 4 |
| Membership dates | New membership starts on verified activation unless an explicit start date is chosen; renewal extends current coverage. Define month-end and expired-renewal behavior. | 6 |
| Payment exceptions | Rejected proof, wrong amount, duplicate reference, payment to old QR, cancellation and externally processed refunds. | 6 |
| PT capacity | Count distinct active assigned clients per trainer per gym, including owner-coaches. Define per-session clients, reservations and expiry; do not silently apply gym limits to independent coaches. | 7 |
| PT service terms | Session duration, what duration packages include, cancellation/no-show rules and trainer removal/reassignment. | 7 |
| Manual verification delay | Set reservation rules and a paid-but-unfulfillable exception process; never silently discard a received payment if eligibility/capacity changes. | 7 |
| Notification delivery | Confirm push targets and provider/runtime choice; proposed mobile push first, with web inbox. Browser push is a separate decision. | 9 |

Acceptance: user reviews the foundations and designs. Unresolved later-step decisions remain explicit instead of becoming invented defaults. Do not start application code in this step.

### Step 1 — Business model and migration

Slices: (1) additive organization/relationship schema; (2) migration rehearsal/backfill; (3) repository scoping and constraints.

Introduce organizations of type gym or coaching business; user-to-organization relationships and role assignments; organization-scoped member/client records; separate trainer-client assignments. Keep personal identity separate from paid membership and employment status. Do not require online clients to purchase gym membership.

Backfill existing coaching ownership with a deterministic mapping and preserve client/plan/progress/analysis identifiers and history. Do not merge client records automatically using names. Linking a legacy client to a login requires a verified invitation/claim process. Resolve unowned analysis/job/media records explicitly rather than making them visible across businesses.

Use new Flyway versions after the current highest version at implementation time. Do not rewrite V1/V2. Use an expand/backfill/switch approach, retain compatibility where required, and defer destructive cleanup. Rehearse on a database copy and keep a backup/restore procedure; application rollback must remain compatible with the expanded schema.

Acceptance: old coaching records remain accessible to the correct users; row counts and relationships reconcile; fresh installation and upgrade both succeed; cross-business identifiers are rejected. No production migration in this step without a separate deployment review.

### Step 2 — Accounts and permissions

Slices: (1) identity/session changes; (2) permission enforcement across existing endpoints; (3) web navigation and business context.

Remove the universal coach-profile requirement from generic authentication. Check current organization relationship and status on protected operations so PT deactivation takes effect for already-issued sessions. Never trust a selected business ID or hidden UI element as authorization.

Apply isolation to clients, plans, drafts, PDFs, progress photos, uploads, analysis jobs, downloads and asynchronous workers. Carry organization context into background jobs. Review existing query-string access tokens and development secret fallback before production; select a secure download/session approach. Clear or namespace cached client selections when changing business or logging out.

Acceptance: owner can administer and coach in one interface; PT sees only assigned clients; member sees only their own data; forged business/client IDs fail; PT removal revokes PT permissions without removing unrelated member/business access; legacy coach flows still work.

### Step 3 — Email and invitations

Slices: (1) durable notification outbox and ACS adapter; (2) verification/recovery; (3) expiring staff invitations.

Introduce retryable background email delivery without blocking business transactions. Configure sender identity and environment placeholders in approved example files only. Real secrets stay in ignored local settings or secure deployment configuration. Expose delivery failures for operational review without leaking tokens or sensitive contents into logs.

Invitations identify business, recipient and permitted role. Verify recipient control; acceptance must support existing and new accounts and be single-use. Handle expired/revoked invitations. Password recovery should use short-lived single-use tokens, avoid account enumeration and define session invalidation.

Acceptance: mocks cover retries, duplicate work and invalid tokens; cross-recipient invitation acceptance fails. Real ACS sender/domain configuration and delivery must pass before public onboarding is enabled. Add later email templates only for the agreed event scope.

### Step 4 — Vectra software subscriptions

Slices: (1) business-type selection and pending onboarding; (2) Razorpay test checkout and signed events; (3) renewal/failure/cancellation lifecycle.

Create a personal account and pending business before checkout; resume abandoned signup. Maintain separate software plan catalogues for gyms and online coaches. The subscription belongs to the business, not every staff account. Use Vectra's merchant account for these payments.

Use provider-hosted authorization and store provider customer/subscription references and billing state, never card credentials, CVVs or UPI PINs. Distinguish mandate authorization from the first paid billing period. Confirm payment and plan/amount/currency association on the backend before activation. Preserve payment history and paid-through dates.

Persist and deduplicate signed webhook events; handle retries and out-of-order delivery without duplicate activation or extending access twice. Add reconciliation for missed events. Cancellation of future renewals must not erase paid history. Define grace/restricted states before implementing them.

Acceptance: test success, abandoned signup, authorization-only, failed renewal, duplicate/out-of-order events, cancellation and recovery. Live credentials and provider enablement are release gates, not prerequisites for mock development.

### Step 5 — Gym setup and member onboarding

**Implemented:** see [Step 5 completion report](GYM_MANAGEMENT_STEP_5_REVIEW.md) for behaviour, verification and release order.

Slices: (1) branding and catalogues; (2) public join page/account linking; (3) registration QR image and reception poster download.

Admin configures gym plans, per-trainer PT plans, payment QR, recipient name and UPI ID. Limit payment-destination changes to authorized users and audit changes. Validate uploads and show a preview for owner confirmation.

Give each gym a stable public registration identifier. Link and QR share one mobile-friendly onboarding page. Renaming the gym must not break existing printouts. Show explicit registration-unavailable states where necessary. Public endpoints expose only intended gym catalogue/profile data, never member/staff private records.

Create pending purchases with immutable price/terms snapshots and amounts in integer paise. Existing users sign in rather than create duplicate accounts. Changing catalogues or payment QR must not silently alter an existing pending purchase's recorded instructions/terms; provide an explicit refresh/review path.

Acceptance: onboarding works on phone and desktop without installing an app; two gyms show their own catalogues and payment destinations; printed QR scans correctly; signup creates no paid entitlement by itself.

### Step 6 — Payment verification and memberships

Slices: (1) payment submission and verification queue; (2) atomic confirmation/activation; (3) expiry, renewal and exception handling.

Track purchase, payment verification and membership entitlement separately. Suggested purchase flow: pending payment → awaiting verification → confirmed, with explicit rejected/cancelled states and recoverable corrections. Do not equate failed email delivery with failed purchase.

Members may submit a reference and optional evidence; screenshots are not proof of receipt. Admin checks the owner's merchant/bank transaction, records actual amount/reference/date, and uses Confirm payment and activate membership. Cash requires an authorized received-cash record. Preserve verifier, timestamps, payment method and an audit trail. Do not rely on automatic access to the owner's UPI notifications.

Prevent transaction-reference reuse within a gym and duplicate confirmation. Commit payment confirmation and entitlement activation atomically; enqueue confirmation email in the same durable transaction boundary. Show pending submissions separately from confirmed collections. Refunds are initially performed outside Vectra and recorded with their entitlement consequences; do not imply bank refunds are automatic.

Acceptance: repeated/concurrent admin confirmations activate once; unpaid/rejected purchases stay inactive; new membership and renewal dates match agreed rules including month-end/leap-year cases; expiry reminders are deduplicated. Audit corrections without deleting payment history.

### Step 7 — PT packages and appointments

Slices: (1) trainer catalogue/assignment; (2) verified PT purchase with eligibility/capacity; (3) appointments and trainer reassignment.

Disable duration packages whose end date exceeds paid gym coverage, explain the date requirement and link to renewal. Enforce the rule server-side at purchase and verification. Per-session appointment dates must fit paid membership coverage. Independent online coaching bypasses gym-membership eligibility.

Enforce the agreed 10-client counting rule transactionally, including concurrent purchases. A pending payment cannot reserve capacity indefinitely. Define reservations before accepting payments and surface late payments for admin resolution when a slot is no longer available. Do not confirm an unusable PT package automatically.

Appointments support booking, rescheduling, cancellation and completion with overlap checks and explicit session consumption rules. Trainer removal revokes access while preserving records and giving the admin a reassignment queue. Store timestamps consistently and display India-local dates/times; duration membership dates use the agreed calendar rules.

Acceptance: two purchases cannot both take the final slot; membership expiry is rechecked after delayed verification; duplicate session completion does not consume twice; overlapping appointments fail; trainer removal and online-coach flows work.

### Step 8 — Coaching access, reporting and inbox

Slices: (1) member access to existing coaching features; (2) owner reporting; (3) persistent inbox and audience targeting.

Reuse existing services for workout/nutrition plans, goals, progress photos, approved AI drafts, movement analysis and PDFs. Add role-aware client access without weakening tenant isolation. Keep draft/private coach material separate from published member content.

Owner reports show confirmed UPI/cash collections, refunds, active/expiring memberships and PT purchases. Distinguish cash collections from accounting revenue recognition. Manually verified records are not a live bank balance or automatic bank reconciliation. PTs must not acquire financial/admin permissions through their coaching access.

Persist notifications with business, recipient, event identity and read status. Target audiences on the server; use stable deduplication keys. Announcements remain within the sender's business. Build expiry reminders and billing notices from authoritative dates/state.

Acceptance: existing analysis/plan workflows remain functional; report totals reconcile with confirmed records and refunds; members cannot read others' inbox entries; event retries do not duplicate messages. Implemented expiry policy: active business relationships retain published plans, goals and progress history after gym/PT expiry. New member uploads require an active client profile and current gym/PT coverage; independent coaching has no gym entitlement gate. Private goal notes and AI drafts remain staff-only. Verified client invitations link existing coaching profiles without granting staff roles.

### Step 9 — React Native and push (deferred entirely)

Slices: (1) mobile scaffold, authentication and business context; (2) member journeys; (3) PT/admin journeys; (4) push and notification deep links.

Select the React Native runtime, navigation and push provider with current documentation before coding; record the choice. Introduce a mobile directory only at this step. Share API contracts/design tokens where useful, not browser-specific UI implementations. Maintain the same domain rules in the backend.

Deliver login, gym onboarding handoff, membership/PT status, payment instructions, plans, progress, appointments and inbox. Provide PT client/appointment tools and the owner's integrated administrative capabilities on mobile with navigation adapted to screen size. QR shown on the user's phone needs copyable UPI details/payment instructions as an alternative to scanning that same screen.

Store device registrations per user/device; handle permission denial, token rotation, logout and invalid tokens. Push is an alert for a persisted inbox item, not the source of truth. Recheck access when a deep link opens, including revoked PT roles. Avoid sensitive coaching/payment details in lock-screen previews.

Acceptance: test Android and iOS on real devices, multiple devices, denied permissions, expired sessions and revoked access. Review current app-store rules for Vectra software purchases versus physical gym services and online coaching before choosing mobile purchase entry points. Do not assume web checkout can be embedded for every product category.

### Step 10 — Web pilot and release

Slices: (1) staging migration/deployment rehearsal; (2) two-gym and one-online-coach pilot; (3) monitored production release.

Use separate test/live provider settings. Verify live Razorpay subscriptions, actual ACS delivery, storage access and analysis/email/billing/reminder worker deployment. Push credentials are deferred. Confirm database backup and restore, migration order and rollback compatibility. Recheck current GitHub Actions workflows rather than assuming image publication deploys the API or worker.

Pilot with owners, additional admins, PTs and members, including a person with several roles/businesses. Exercise UPI/cash verification, renewals, PT limits, failed billing, duplicate events, provider outages and role revocation. Use explicit business feature flags to stage rollout and disable new purchase entry points if needed while preserving history.

Acceptance: migration evidence, permission checks, desktop/phone browser flows and provider verification are recorded; support can diagnose pending verification, failed email and billing reconciliation. Local readiness tooling does not substitute for live-provider verification or a real-user pilot. Native real-device and push checks are deferred.

## Proposed domain boundaries

Use services for business rules, repositories for persistence and `app.py` for HTTP routing, matching repository conventions. Suggested domains are identity, organizations/access, invitations, catalogues, purchases/manual payments, memberships, trainer assignments/appointments, SaaS billing and notifications. Retain existing coaching/analysis domains.

Conceptual records include organizations; organization users/roles; member profiles; invitations; catalogue versions; purchase snapshots; payment verification/audit records; membership periods; PT entitlements and assignments; appointments; software subscriptions/provider events; inbox items; delivery outbox; and device registrations. Final table names and API contracts are Step 0/1 deliverables, not a requirement to create all tables upfront.

## Configuration plan

Add placeholders only when the owning step is implemented. Never create usable-looking fake secrets or commit real credentials.

| Proposed setting | Introduce in |
| --- | --- |
| Public web/app base URL for registration/invitations | 3, 5 |
| `AZURE_COMMUNICATION_SERVICES_CONNECTION_STRING` and `AZURE_COMMUNICATION_SERVICES_SENDER_ADDRESS`, or an explicitly selected managed-identity alternative | 3 |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | 4 |
| Push provider credentials and Android/iOS application identifiers | 9 |

These Razorpay credentials belong to Vectra's software billing. No gym Razorpay credentials or merchant-connection flow is required for this release's manually verified UPI/cash collections. Future automated gym collections require a separate provider/onboarding design.

## Verification standards

- Backend changes: targeted unittest regression tests with in-memory repositories/mocks, then the applicable broader suite using `mobility-ai-service/venv/bin/python` when available. Run from the backend directory with `venv/bin/python -m unittest discover -s tests`.
- Database steps: real isolated PostgreSQL migration and concurrency checks in addition to mocks. Test clean install, existing-data upgrade, uniqueness and atomic confirmation/capacity enforcement.
- UI changes: `npm run lint` and `npm run build` from `vectra-ui/`, plus browser walkthroughs and screenshots for changed screens.
- Mobile: establish lint/type checks and meaningful tests when scaffolding; test actual Android/iOS builds and real push delivery.
- Preserve regression coverage for authentication, queue lifecycle, coaching ownership, plans and movement analysis. Explicitly test cross-business access and removed-staff access.

## Deferred work

React Native Android/iOS apps, mobile push/device registration/deep links and app-store delivery; automated gym Razorpay merchant connections/QR confirmation; per-gym dedicated apps/custom domains; branch management; trainer payouts/commissions; configurable PT capacity; biometric attendance; WhatsApp integration; and general marketing email campaigns are outside this implementation sequence unless separately approved.

## Next session

Continue with the external web-release gates in [WEB_RELEASE_RUNBOOK.md](WEB_RELEASE_RUNBOOK.md): Azure interactive login refresh, target-environment migration/restore rehearsal, deployed worker verification, live ACS/Razorpay evidence and the two-gym/one-coach pilot. No mobile work is required for web release. No live provider charges or production data were changed during the web implementation.
