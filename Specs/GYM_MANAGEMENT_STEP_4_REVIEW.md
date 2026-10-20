# Step 4 — Business software subscriptions

Implemented 18 October 2026. Step 4 is complete at the local implementation and synthetic-provider verification boundary. Step 5 and deployment have not started. Real Razorpay test-mode checkout, merchant enablement, production credentials and real ACS email delivery remain release gates.

## Delivered behavior

- Personal registration saves a pending gym or independent-coaching business and owner relationship before checkout. Existing verified accounts can add businesses. Request IDs make retries idempotent; signing in resumes saved onboarding. Staff do not purchase individual software subscriptions.
- Owner billing uses separate configurable catalogues by business type. The immutable checkout snapshot records price in integer paise, INR, period, interval, cycle count, grace and accepted terms version/time. Changing the catalogue does not rewrite an existing attempt.
- Razorpay-hosted checkout collects authorization details. Vectra stores provider references and verified history, never card credentials or UPI secrets. Browser success is only a request to reconcile, not an access grant.
- The backend verifies the remote plan, business/attempt association, subscription, paid invoice, captured payment, amount, currency, order/invoice linkage and service dates before recording coverage. Authorization-only invoices grant no service period. Unsupported or inconsistent provider data fails closed.
- Signed raw-body webhooks are persisted and deduplicated before acknowledgement. Current provider data is fetched by the worker, so duplicate, delayed and out-of-order events cannot extend access twice. Scheduled reconciliation repairs missed events, including refund changes.
- Subscription creation is durable and leased. A timeout or crash with an unknown creation outcome triggers discovery by attempt ID, never an automatic second create request. Concurrent checkout calls share one open attempt per business/mode.
- Cancellation stops renewals and retains history/paid coverage. Cancelling before provider creation closes locally without creating a remote subscription; refresh cannot reopen it. Reactivation after a closed subscription schedules after existing paid coverage.
- Paid, refund, failure-state and cancellation notices enter the existing durable email outbox. Notice persistence and payment recording are atomic; external email delivery failures retry independently and never revoke recorded payment.
- Owner-only financial controls, scoped summaries for other relationships, backend billing restrictions, blue UI, test-mode labels, resumable checkout and verified payment history are implemented. Financial details are excluded from non-owner summaries.

## Commercial defaults and access policy

These are explicit implementation defaults, not approved production pricing. No live price or provider plan is checked in. `SOFTWARE_PLANS_JSON=[]` disables checkout while keeping onboarding and legacy workspaces available.

| State | Behavior |
| --- | --- |
| Pending | A new business has no verified paid period; operational endpoints return 402. Account, verification and owner billing remain available. |
| Active | A verified, not fully refunded period covers the current instant. |
| Grace | Default seven days after the last paid period, snapshotted per subscription; writes remain available. Configurable from 0–30 days. |
| Read-only | Grace expired, a paid period was fully refunded, or a legacy deadline elapsed. Existing records remain readable; operational writes return 402. Staff/invitation revocation remains available. |
| Legacy | Pre-V8 businesses retain access until an explicit operator transition deadline or their first verified payment in the configured mode. |

Cancellation does not automatically refund. Refunds require support review and provider-side processing. Full refunds remove that invoice's coverage; partial refunds preserve its service dates. History remains. Grace follows the paid-period policy even following cancellation. Test payments never grant live-mode access. Gym membership/PT collections remain separate and are not implemented here.

Legacy businesses are not silently charged or blocked by V8. The operator transition command requires at least 30 days notice and queues an owner notice. Before setting a deadline, confirm deliverability and communicate the published commercial terms.

## Configuration and operation

Apply Flyway V8 before deploying the updated API or email/billing workers. The email outbox now supports either an identity action or a billing notification. Retain the existing stable `AUTH_TOKEN_SECRET`, database and ACS settings.

Set these through deployment configuration/secrets, never committed credentials:

- `RAZORPAY_MODE`: `test` initially; `live` only after release checks.
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`: Vectra merchant credentials matching the mode.
- `RAZORPAY_WEBHOOK_SECRET`: independent configured webhook signing secret.
- `SOFTWARE_PLANS_JSON`: array with `code`, `name`, `business_type` (`gym` or `coaching`), `amount_paise`, `period` (`monthly` or `yearly`), `interval`, `total_count`, `razorpay_plan_id`. Create and verify matching provider plans first. Amounts must match the whole invoice; this implementation intentionally does not support taxes/add-ons that change the invoice total or extra invoice lines.
- `SOFTWARE_BILLING_GRACE_DAYS`: default `7`.
- `SOFTWARE_TERMS_VERSION`: default `software-v1`; update for changed published terms. UI consent resets when displayed terms/catalogue changes.

Run from `mobility-ai-service/`:

```sh
venv/bin/python billing_worker.py
venv/bin/python billing_worker.py --once
venv/bin/python email_worker.py
venv/bin/python scripts/billing_admin.py
venv/bin/python scripts/email_outbox.py
```

Expose `POST /webhooks/razorpay` over HTTPS in the correct environment. Configure subscription lifecycle events and the same webhook secret. The endpoint verifies `X-Razorpay-Signature`, requires `X-Razorpay-Event-Id`, and bounds the raw payload to 256 KiB. It stores sanitized event metadata and a body hash, not the raw payload. Non-subscription events are acknowledged but do not activate access; periodic invoice/payment reconciliation observes refunds.

The worker polls for due work every five seconds, uses five-minute leases, and reconciles known subscriptions every fifteen minutes. Storage/provider failures retry with bounded backoff and sanitized error codes. Monitor worker health, pending events, `updated_at`, `next_sync_at` and error metadata, email failures and reconciliation lag. Provider outages preserve recorded coverage; they do not manufacture new coverage.

Operator recovery, with the same environment/mode as the affected business:

```sh
venv/bin/python scripts/billing_admin.py --retry SUBSCRIPTION_UUID
venv/bin/python scripts/billing_admin.py --resolve-creation SUBSCRIPTION_UUID
venv/bin/python scripts/email_outbox.py --retry OUTBOX_UUID
venv/bin/python scripts/billing_admin.py --legacy-organization ORGANIZATION_ID --legacy-until UTC_ISO_TIMESTAMP
```

If discovery finds no remote subscription, inspect the merchant dashboard and provider records before using `--resolve-creation SUBSCRIPTION_UUID --confirm-no-remote`. This explicit operator resolution closes the failed attempt so the owner can start again. Never use it merely because a network request timed out. Operations are audited. Do not manually insert paid records to bypass verification.

## Verification

Automated coverage includes fresh/upgrade migrations, legacy preservation, business/checkout concurrency, authorization-only payments, successful activation, price/association mismatch, atomic rollback, renewal failure/grace/expiry/recovery, cancellation/reactivation, cancellation before creation, ambiguous-create recovery, webhook HMAC/deduplication/out-of-order replay, missed-event reconciliation, full/partial refund, cross-business/owner permissions, test/live separation, real ASGI billing restrictions, and notification delivery without identity tokens.

Browser checks use the actual React app against an isolated synthetic localhost API: pending billing, consent enabling a plan, saved queued checkout, cancellation/reactivation, read-only workspace and business-type onboarding. No external checkout or payment was submitted. The preview's example price is fictional and is not deployment configuration.

Final verification passed:

- Backend: `cd mobility-ai-service && venv/bin/python -m unittest discover -s tests` — 71 tests.
- Database: `VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python -m unittest discover -s database/tests -v` — 72 tests, including 17 Step 4 database tests, in 210.660 seconds. Disposable PostgreSQL/Flyway fixtures only.
- Frontend: `npm run lint` and `npm run build` — passed.
- Python source syntax checks and `git diff --check` — passed.
- Browser walkthrough — passed with no console errors. Temporary preview servers were stopped after checking.

## Release and rollback boundary

1. Publish the real catalogues, recurring terms, refund/support policy and legacy transition policy; configure matching Razorpay test plans.
2. Back up/rehearse the database migration, apply V8, then deploy the matching API and both durable workers. Existing analysis worker remains separate.
3. In Razorpay test mode, verify actual checkout, mandate-only behavior, captured first/renewal invoices, recovery, cancellation response semantics, signed delivery/replay and refund reconciliation against real provider payloads. Verify the documented invoice-period bounds with the chosen monthly/yearly plans.
4. Verify ACS sender/domain and actual notice delivery. Confirm monitoring and operator recovery permissions. Only then configure live credentials/plans and a live webhook endpoint through the normal release process.
5. Do not downgrade to a pre-Step-4 API that bypasses billing enforcement. Roll back to a compatible build or pause new checkout while retaining reconciliation, history and billing restrictions. Do not drop V8 tables or restore away financial history after provider charges. Resolve discrepancies using reconciliation/audited operations.

No real merchant resources, emails, charges, production data or deployment were changed during implementation.

Provider references: [subscription creation](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/), [cancellation](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/), [subscription invoices](https://razorpay.com/docs/api/payments/subscriptions/fetch-invoices), [subscription entity](https://razorpay.com/docs/api/payments/subscriptions/entity), [webhook validation](https://razorpay.com/docs/webhooks/validate-test/).
