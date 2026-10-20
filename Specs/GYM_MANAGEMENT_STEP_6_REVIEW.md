# Step 6 — Payment verification and memberships

Implemented locally on 2026-10-20. Existing tracked and untracked work from Steps 0–5 was preserved. No application database migration, deployment, live payment request, or live email delivery was performed.

## Behavior and decisions

- Purchase snapshots remain immutable. Purchase status, append-only payment events, verified receipts, and membership periods are separate records.
- Members submit a reference and details, optionally upload up to five sanitized PNG/JPEG evidence images, cancel an unconfirmed purchase, and resubmit after rejection. Evidence is private, tenant-scoped, and never treated as proof of receipt.
- Owners/admins check the actual merchant/bank receipt or cash received, record method, actual amount, normalized reference/receipt number, receipt date and a verification note, then choose **Confirm payment and activate membership**. Trainers and member mode cannot perform these actions.
- Confirmation requires the exact frozen purchase amount. Wrong amounts are rejected with a recorded reason and resolved outside Vectra before resubmission. Old-QR payments are checked against the original snapshot recipient, not the current catalogue. A correction adds an audit note; it never rewrites the original receipt or releases its reserved reference.
- A gym profile row lock serializes confirmation and renewal calculations within that gym. A database uniqueness constraint also prevents reference reuse within a gym. Repeated confirmation returns the existing result. Receipt insertion, membership activation, purchase status, audit event and notification/outbox insertion share the request transaction; an enqueue failure rolls all of them back. Subsequent email delivery failure does not undo a purchase.
- New coverage begins on the India-local verification date, or an explicit future start date. Backdating is rejected. Receipt dates must fall between purchase creation and verification day.
- Dates use half-open periods: `starts_on <= date < ends_before`. Renewals begin at the later of the requested/default start and the latest non-revoked paid end date. Expired renewals start today. Existing future periods keep their dates, including after another period is refunded.
- Add 1/3/6/12 calendar months and clamp the day to the destination month's last day. For example, 31 January 2024 + 1 month ends before 29 February 2024; 29 February 2024 + 12 months ends before 28 February 2025. Each renewal computes from its actual start; there is no separate original-day anchor.
- Membership state is derived as scheduled, active, expired or revoked. Expiration does not depend on a worker changing a status field.
- Full refunds are performed externally, then recorded with amount, reference, reason and an explicit revoke/retain decision. The verified receipt and audit remain intact. Partial refunds and editing booked financial values are not offered; operators can append exception/correction notes. Vectra never transfers refund money.
- Purchases containing PT are retained but cannot be confirmed in Step 6. They must await Step 7 eligibility/capacity resolution, even if a member has already paid. The UI explicitly tells admins to retain the receipt and not request another payment. No PT entitlement or capacity is granted.

## Database and API

New migration: `database/migrations/V10__manual_payments_memberships.sql`, after V9. Adds payment events, verified receipts, membership periods, tenant foreign keys, immutable payment-history triggers and expanded purchase states. Existing V1–V9 files were not changed by Step 6.

Member endpoints:

- `GET /member/purchases/{id}`: own payment audit and membership dates/status.
- `POST /member/purchases/{id}/submit` or `/cancel`.
- `PUT /member/purchases/{id}/evidence`: bounded sanitized image upload.

Admin endpoints:

- `GET /gym/purchases/{id}`.
- `POST /gym/purchases/{id}/confirm`, `/reject`, `/cancel`, `/refund`, `/correct`.
- `GET /gym/purchases/{id}/evidence/{event_id}`: protected evidence, never a public asset.

All routes use existing selected-business authorization, active relationships, role checks and software subscription write gates. The public registration/history route exposes no evidence or payment ledger. Private responses are non-cacheable.

`membership_worker.py` is a one-shot daily reminder enqueue command using existing PostgreSQL configuration. It enqueues deduplicated seven-day and one-day expiry notices, suppressing notices where another unrevoked period continues coverage. It sends nothing itself. The existing email worker handles the durable outbox with its established retry behavior. No scheduler or live email worker was started. No new provider credentials are required.

The UI adds a verification queue and separate confirmed/history section to gym setup, and payment submission, evidence upload, membership dates, renewal navigation and audit history to the member workspace. It preserves the existing theme. Lists retain the existing latest-100-record limit.

## Verification

Tests use throwaway Docker PostgreSQL databases and generated fixture identities (`example.invalid`). They do not load application database settings. Docker Desktop was started because its daemon was initially stopped. The test harness removes its own containers and networks.

Passed:

- Full isolated PostgreSQL/Flyway suite: **95 tests**, including the initial nine Step 6 tests (`/tmp/vectra-step6-all-db.log`).
- Expanded final Step 6 suite: **12 tests**, including actual ASGI routes, role/tenant/privacy checks, concurrent confirmation, reference uniqueness, rejected/cancelled/PT inactivity, rollback on notification failure, renewal dates, refunds, immutable history and reminder deduplication (`/tmp/vectra-step6-db.log`). These overlap the full suite; they are not 12 additional independent tests.
- Backend unittest suite from `mobility-ai-service`: **81 tests**, including calendar boundary cases (`/tmp/vectra-step6-backend.log`).
- Frontend `npm run lint` and `npm run build`.
- `git diff --check`.

Commands:

```sh
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python -m unittest discover -s database/tests -v
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python -m unittest discover -s database/tests -p test_memberships.py -v
cd mobility-ai-service
venv/bin/python -m unittest discover -s tests -v
cd ../vectra-ui
npm run lint
npm run build
```

 Browser visual inspection was attempted against a localhost-only preview with fully mocked requests; the in-app browser rejected the URL with `ERR_BLOCKED_BY_CLIENT`. No screenshot or successful visual walkthrough is claimed.

## Release boundary

Apply V10 before running the updated API in a future authorized deployment. Schedule the reminder enqueue command daily only as part of that deployment. Real ACS delivery and earlier software-billing provider release gates remain unverified. Step 7, production migration and deployment have not been started.
