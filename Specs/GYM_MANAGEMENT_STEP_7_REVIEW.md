# Step 7 — PT packages and appointments

Implemented locally on 2026-10-20, preserving the existing working-tree changes from Steps 0–6. This step adds V11, PT purchase eligibility and reservations, atomic verified activation, appointments, and consented reassignment. No deployment, application database migration, live provider request or real email delivery was performed.

## Approved service rules

The user explicitly accepted these initial rules in this chat:

- Appointments last 60 minutes.
- Duration packages allow one appointment per India-local calendar day.
- A single-session credit expires 30 days after activation, or earlier if paid gym coverage ends.
- Cancellation does not consume credit. Only staff completion after the scheduled end consumes it. No automatic no-show consumption or penalty is applied.
- A pending purchase reserves capacity for 24 hours.
- Trainer reassignment requires recorded member consent.

These terms are saved in new PT purchase snapshots and shown before checkout. Existing snapshots remain immutable. Legacy PT purchases without these terms require an explicit admin record of member consent before confirmation.

## Purchase, eligibility and capacity

A member can buy PT alone using existing paid membership, or include it with a gym purchase when existing paid coverage already satisfies PT eligibility. A pending gym purchase is never treated as paid coverage. Newly joining members must first have gym payment verified. Public checkout disables unavailable PT options, displays paid coverage and the reason, and explains the renewal path.

Eligibility combines adjacent/overlapping non-revoked membership periods and rejects gaps. Duration PT must fit the full calendar-month period. Single-session validity is capped by continuous paid coverage. Both checkout and delayed receipt verification repeat these checks. Appointment booking, rescheduling and completion also check the appointment's full interval against paid coverage.

Capacity counts distinct members per trainer per gym, including owner/admin coaches. Multiple packages for the same member count once. Unexpired, usable entitlements (including scheduled packages) and live pending/awaiting-verification reservations count; exhausted credits, revoked entitlements, removed-trainer work, inactive members, cancelled/rejected purchases and expired reservations do not. Capacity is conservatively held for future scheduled packages; it is not divided into future time buckets.

Purchase creation, confirmation and reassignment serialize on the gym profile lock. Database transactions prevent two purchasers from taking the final slot. Rejection/cancellation releases the reservation; resubmission does not silently renew it. Expired reservations require a fresh capacity check at confirmation. Independent coaching has neither a gym-membership gate nor the gym's ten-client limit.

Successful confirmation writes the verified payment, PT entitlement, member client profile/link if needed, trainer assignment, audit and notification outbox atomically. If coverage, terms or capacity fail, the purchase remains unconfirmed with a durable resolution reason and receipt-report audit; it grants no entitlement and no confirmed collection. Admins can record consented reassignment, resolve membership coverage and retry, or record a full external refund. No second payment is requested automatically and no refund money is moved by Vectra.

## Appointments, access and reassignment

Booking uses an idempotency key. Rescheduling uses a version guard. Trainer/client overlaps are checked under the business mutation lock. A single credit cannot support two simultaneous outstanding bookings. Repeated/concurrent completion changes the status and decrements credit once, in the same transaction; cancellation releases a booking without decrementing credit. UTC timestamps are stored and India times displayed/input explicitly.

Owners/admins manage their business. Trainers see only their assigned PT work, without financial amounts or payment references. Members see their own packages and appointments. All operations retain selected-business authorization and the existing software subscription write gate. Independent coaching uses existing client/trainer assignments.

Role/relationship revocation durably marks affected PT entitlements for reassignment, cancels booked appointments without consuming credit, and ends trainer-client assignments. Re-granting the role alone does not restore the old PT work. Member identity and other-business access remain independent. The admin PT workspace shows the reassignment queue and retains historical records.

Reassignment preserves purchase prices/terms, entitlement dates and remaining credits, records consent, checks the replacement trainer's capacity, cancels this package's bookings, and creates the replacement assignment. Members must rebook. The original purchase snapshot is not rewritten. Historical coaching access policy remains a Step 8 decision.

## Implementation

- `database/migrations/V11__pt_packages_appointments.sql`: reservation/resolution state, PT entitlements, appointments, audit and durable revocation triggers. Prior migration files were not edited.
- `repositories/pt_repository.py` and `services/pt_service.py`: tenant-scoped persistence and PT/appointment rules.
- Existing gym onboarding and manual confirmation services now call the PT rules. Step 5/6 tests were updated where the new paid-coverage requirement intentionally tightens checkout.
- `GET /pt/workspace`, `GET /member/pt-options`, and authenticated `GET /public/gyms/{public_id}/pt-options`.
- `POST /appointments` and `POST /appointments/{id}/{reschedule|cancel|complete}`.
- `POST /gym/purchases/{id}/reassign-pt` (registered before the generic payment-action route).
- Staff Sessions and member workspaces now expose packages, appointments and reassignment. Gym verification exposes pending-payment resolution and external-refund recording. Existing blue styling remains.

No new dependencies or environment settings are required. V11 must precede the updated API in a separately authorized deployment. Workspace lists are bounded to 200 entitlements/appointments; payment lists retain their existing 100-record limit.

## Verification and boundaries

Tests use disposable PostgreSQL/Flyway resources, generated fixture accounts and mocked providers. They never read the application database connection settings or send real emails. Passed:

- Full isolated PostgreSQL/Flyway suite: **111 tests** (`/tmp/vectra-step7-database.log`).
- Final focused PT suite: **14 tests** (`/tmp/vectra-step7-pt-final.log`), including HTTP authorization, simultaneous last-slot purchase, expired-reservation resolution, rejection/resubmission, atomic rollback, duplicate completion, overlap/day limits, trainer revocation/re-grant, legacy-term consent, external-refund records and independent coaching. This overlaps the full suite and includes the final focused fixes; the counts are not additive.
- Backend unittest suite: **83 tests** (`/tmp/vectra-step7-backend.log`).
- Frontend `npm run lint` and `npm run build`.
- `git diff --check`.

Reproduce from the repository root (Docker must be running for database tests):

```sh
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python -m unittest discover -s database/tests -v
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python -m unittest discover -s database/tests -p test_pt_appointments.py -v
cd mobility-ai-service
venv/bin/python -m unittest discover -s tests -v
cd ../vectra-ui
npm run lint
npm run build
```

Visual browser verification remains unconfirmed: only the in-app browser is available, and the localhost preview was blocked by `ERR_BLOCKED_BY_CLIENT` in this chat. No screenshot or successful browser walkthrough is claimed. Frontend lint/build and HTTP/service/database checks cover the available local verification boundary.

Step 8, deployment, provider integration and notification delivery remain outside this step.
