# Step 3 — Email, verification, recovery and staff invitations

Implemented locally on 2026-10-18. All three Step 3 slices are complete. Step 4 and deployment are not included. Existing Step 1–2 working-tree changes are preserved.

## Delivered behavior

- V7 adds identity action records, a durable email outbox, request throttling and identity verification/session-version fields. Account creation, invitation creation and their outbox records commit atomically. ACS is called only by the separate email worker.
- The worker claims pending deliveries with PostgreSQL `FOR UPDATE SKIP LOCKED`. It retries provider failures five times with exponential backoff, keeps a stable provider operation ID across retries, cancels expired/used/revoked actions and exposes sanitized failure metadata. `sent` means ACS reported successful submission, not proof of inbox delivery. A crash between provider submission and the database commit can cause a repeated email; authorization effects remain single-use.
- Verification links last 24 hours. New coach accounts can sign in and resend verification but cannot access business APIs until verified. Accounts existing before V7 retain access without falsely marking their email verified. Existing sessions continue to work until expiry or password reset.
- Recovery links last 30 minutes. Known and unknown addresses receive the same response. Requests have a per-address/purpose one-minute cooldown and a persisted per-peer limit of 20 identity requests per hour. A successful reset increments the account's session version, invalidating all previously issued sessions and older verification/recovery actions. It does not automatically sign the user in. Passwords created through these flows require 12–256 characters; existing passwords remain usable.
- Invitations last 3 days and identify one recipient, business and role. Owners may invite admins or trainers; admins may invite trainers. Ownership is not an invitation role. Existing accounts must authenticate as the exact recipient. New recipients create a personal account directly from the invitation, without creating a separate coaching business. Acceptance proves email control and atomically grants the role. It never claims legacy client records or grants paid membership.
- Acceptance rechecks the issuer's current relationship, business status and privileges. Inactive recipient relationships are not silently reactivated. Repeated/concurrent acceptance succeeds once. Owners/admins can inspect delivery and acceptance state and revoke eligible invitations; trainer/member accounts cannot manage invitations. Sending a replacement for the same role revokes the prior unused invitation, subject to the cooldown.
- The web app includes verification/resend, recovery, invitation acceptance for existing/new accounts, account switching and invitation management. It handles email links opened in an already-running app tab. Link tokens are removed from the visible URL after loading and held only in memory; reloads require reopening the email link.

## Security and operational boundaries

Action tokens use HMAC with domain separation from session tokens and a random action UUID. The database stores token hashes and action metadata, never raw links or message bodies. The worker reconstructs a link only when sending. Links use URL fragments, so their tokens are not included in HTTP access logs or referrers. Tokens are submitted in request bodies; deployment request-body tracing must remain disabled for authentication routes.

The API and email worker must share the same stable `AUTH_TOKEN_SECRET`. Secret rotation invalidates sessions and queued links. Old queued links fail with `signing_key_changed`; issue fresh verification/recovery requests or replacement invitations after rotation. Do not retry those obsolete actions as a repair.

Provider exception text is neither stored nor logged. Operators see action kind, business ID, outbox ID, attempts, status and a fixed error code. Access to the operator CLI requires deployment/database access. The worker intentionally holds only its delivery-row transaction during the bounded provider call; it does not hold a business transaction open while sending.

The rate limiter uses the direct request peer. Configure trusted proxy handling correctly in deployment; otherwise many users behind a proxy may share a bucket. Never trust an arbitrary forwarded-IP header. Expired actions and old throttle buckets may be archived/purged under an operational retention policy; no automatic deletion of audit records is introduced here.

## Configuration and operation

Placeholders were added only to `mobility-ai-service/local.settings.json.example`:

| Setting | Purpose |
| --- | --- |
| `PUBLIC_WEB_BASE_URL` | Canonical frontend URL. HTTPS required except localhost/127.0.0.1 development. No query, fragment or embedded credentials. |
| `AZURE_COMMUNICATION_SERVICES_CONNECTION_STRING` | ACS Email connection, blank in the example. |
| `AZURE_COMMUNICATION_SERVICES_SENDER_ADDRESS` | Enabled ACS sender identity, blank in the example. |

Install `azure-communication-email>=1.1.0,<2` with backend requirements. The adapter was checked against installed SDK 1.1.0 and the [official EmailClient API](https://learn.microsoft.com/en-us/python/api/azure-communication-email/azure.communication.email.emailclient?view=azure-python). Configure actual values only in ignored local settings or deployment secrets. No actual settings or credentials were edited.

From `mobility-ai-service/`:

```bash
venv/bin/python email_worker.py                 # continuous delivery worker
venv/bin/python email_worker.py --once          # process at most one eligible delivery
venv/bin/python scripts/email_outbox.py         # metadata-only pending/failure report
venv/bin/python scripts/email_outbox.py --retry <outbox-uuid>
```

An operator retry is allowed only for a failed, still-valid, unused, unrevoked action. It resets the bounded retry budget while preserving the action and operation IDs. Expired links require a new request/invitation. The analysis worker remains separate. Public APIs do not expose recovery tokens, action lists or a general email-send capability.

## Verification

- Backend unittest suite: 62 tests passed, including retry/terminal failure, duplicate work, expired/consumed/revoked actions, key rotation, malformed tokens, session invalidation, adapter responses and verification gating.
- Full isolated PostgreSQL/Flyway suite: 55 tests passed (195.7 seconds), including the existing migration/authorization regressions. Checks cover clean installation and upgrade through V7, legacy verification transition, atomic signup/outbox rollback, concurrent recovery and invitation acceptance, concurrent workers, retries, cooldowns, cross-recipient rejection, issuer revocation, role restrictions and cross-business revocation rejection.
- Actual ASGI routes against PostgreSQL cover signup, verification, invitation creation/listing/acceptance, staff restrictions, recovery and immediate rejection of old sessions.
- New text/action colors meet WCAG AA normal-text contrast: white on primary blue 5.17:1, secondary blue on pale blue 6.07:1, body text 17.85:1 and error text 8.31:1.
- Frontend `npm run lint` and `npm run build` passed. Browser walkthrough used the actual frontend against a synthetic local API: recovery feedback, staff invitation status/revocation, account switching, new-account invitation form, invalid-link feedback and verification confirmation. These browser fixtures do not establish live ACS delivery.
- Screenshots: `/tmp/vectra-step3-invitations.png`, `/tmp/vectra-step3-recovery.png`, `/tmp/vectra-step3-acceptance.png`, `/tmp/vectra-step3-verification.png`. These are local review artifacts, not committed generated media.

## Rollout, release gate and rollback

1. Back up and rehearse on a restored database, preserving Step 1–2 isolation and queue requirements. Apply V7 after V6 before deploying this API. The only database mutations performed during implementation were against disposable synthetic test databases.
2. Deploy the matching API/web build, configure the three email settings and the shared signing secret, and run the email worker as a separate continuously running process. Existing Docker/CI files were not assumed to deploy a new worker automatically; the worker command must be configured explicitly in the deployment.
3. Verify the ACS resource, sender/domain association, DNS and real delivery to controlled inboxes. Exercise verification, recovery, staff invitations, provider outage/recovery and the failure report. Confirm that links point at the intended web origin. **Actual ACS sender/domain configuration and real email delivery remain mandatory release gates before enabling public onboarding.**
4. Monitor pending age, failed rows and worker health. `sent` is provider submission; investigate recipient delivery using authorized ACS operational tools without exposing email links in application logs.
5. Rollback must retain session-version enforcement, verification gating and tenant permissions. Do not deploy an older API that ignores `session_version` after password resets; that could make revoked sessions valid again. Stop the email worker if needed, retain V7 and its records, and deploy a compatible correction. Do not drop identity/outbox tables or rewrite applied migrations.

No live ACS send, provider setup, Azure deployment or production migration was performed. Step 4 remains pending a separate instruction.
