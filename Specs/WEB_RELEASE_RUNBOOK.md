# Web-only release runbook

Scope: Steps 8 and the web portions of Step 10. React Native, device registration, push, mobile deep links and app-store delivery are deferred. Web onboarding remains usable in phone browsers.

## Current verification boundary

The application implementation and disposable PostgreSQL rehearsal are local. Live staging/production deployment, ACS delivery, Razorpay charges and the real-user pilot are not completed. On 2026-10-20, Azure resource discovery failed with AADSTS700082 (expired interactive login). Cached `az account show` output is not evidence of a working Azure session. No live data, provider payments or deployment settings were changed.

## Release artifacts and order

1. Run frontend lint/build, backend unittest and the isolated database suite. `validate-web.yml` performs validation for PRs without deploying. Configure its jobs as required checks in GitHub branch protection; this repository cannot enforce that setting by itself.
2. Capture the current API/worker immutable image references and web artifact. Verify a target-database backup and restore to an isolated target, including counts and selected historical records. The automated V11 → latest migration and `pg_dump`/restore test is fixture evidence only, not a production backup.
3. Use separate staging/live database, storage, ACS and Razorpay settings. Set `RAZORPAY_MODE=test` for staging and `live` for production. Configure real software plans and merchant eligibility; no commercial prices are invented by this change. Keep secrets in deployment secret references. The same stable `AUTH_TOKEN_SECRET` must reach every API and email-worker replica.
4. Build and publish immutable commit-SHA images. Docker contexts now exclude local settings, environment files, virtual environments and generated output. Apply Flyway through **V13** and validate before starting the new API. V12 adds inbox/rollout records and transactional event mirroring; V13 adds verified client invitations. Do not rewrite earlier migrations.
5. Deploy the API and all workers with the same commit. The existing `deploy-vectra-api.yml` migrates then builds/pushes images; it does **not** update Container Apps. Use the explicit deployment helper below for provisioned targets. The existing Static Web App workflow remains main-push-only. Ensure API/schema readiness before releasing the corresponding web build; its current automatic workflow is not cross-workflow dependency gated.
6. Verify `GET /health/ready` returns HTTP 200 and `{"ready":true}`. This checks database/schema readiness, not external-provider health. Verify worker logs/executions and the provider evidence below.
7. Pilot with two isolated gyms and one independent online coach. Start with each gym's new-purchase control paused where needed, then enable the selected pilot businesses. Never treat a passing build or a test-mode payment as a production pilot.

## Configuration check and explicit container release

Run from `mobility-ai-service` in a shell populated with the **target deployment's** settings. These tools deliberately do not read `local.settings.json` and do not print secret values.

```sh
venv/bin/python scripts/web_release_check.py --environment staging --database
```

The check validates required configuration, mode separation, HTTPS, database TLS, cloud storage and V13, and reports outbox counts. It does not send email or contact the payment provider. Failed email rows are diagnostic evidence, not proof that a new delivery will succeed.

`deploy_web_containers.py` prints its plan by default. Supply the actual subscription/resource names and the full 40-character commit SHA already published to ACR:

```sh
venv/bin/python scripts/deploy_web_containers.py \
  --environment staging --subscription "$TARGET_SUBSCRIPTION" \
  --resource-group "$TARGET_RESOURCE_GROUP" --registry "$TARGET_ACR_SERVER" \
  --commit "$RELEASE_COMMIT" --api "$TARGET_API_APP" \
  --analysis-worker "$TARGET_ANALYSIS_APP" --email-worker "$TARGET_EMAIL_APP" \
  --billing-worker "$TARGET_BILLING_APP" --membership-job "$TARGET_MEMBERSHIP_JOB" \
  --api-url "$TARGET_API_URL"
```

Add `--apply` to execute. The helper requires passing configuration/schema checks, resolves all named resources first, updates API/worker images and commands, and checks API readiness. It does not provision resources, configure identities/secrets/networking, run migrations, deploy the web artifact or automatically roll back partially completed updates. Preserve its output and inspect target revisions after any failure. Staging and production must use their own target arguments and environment variables.

| Process | Image / command | Runtime requirement |
| --- | --- | --- |
| API | `vectra-api:<sha>` / image default | HTTPS ingress, database/storage/OpenAI settings, auth and billing configuration |
| Analysis | `vectra-worker:<sha>` / `python queue_worker.py` | Database, Blob/Queue storage, analysis configuration; no public ingress |
| Email | `vectra-worker:<sha>` / `python email_worker.py` | ACS sender/connection, stable signing secret, database, public web URL; no public ingress |
| Billing | `vectra-worker:<sha>` / `python billing_worker.py` | Razorpay configuration and database; no public ingress |
| Expiry reminders | `vectra-worker:<sha>` / `python membership_worker.py` | Scheduled Container Apps job, at least daily; database. It enqueues notices without contacting providers. |

The deployment helper keeps continuous workers at one replica minimum, so an idle HTTP scaler cannot stop their polling loops. Provision the reminder job's schedule separately. Azure Container Apps job cron schedules use UTC; select the intended India-local delivery time accordingly. Sources: [Container Apps CLI](https://learn.microsoft.com/cli/azure/containerapp?view=azure-cli-latest), [Container Apps jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs).

## Pilot and provider evidence

Record date, environment, release SHA, synthetic/test identity, result and operator for every scenario. Do not place credentials, recovery tokens, payment evidence or private coaching content in this report.

- Two gyms have different catalogues/payment destinations; forged client, plan, photo, PDF, purchase and inbox IDs fail across businesses.
- An online coach invites a client to a specific unlinked profile. The client proves recipient control, receives no staff role, and can use coaching without gym membership. Existing-user, expired, revoked, reused and wrong-recipient invitations fail safely.
- Owner/admin can report and announce. A trainer cannot access reports, announcements or purchase controls. A person with several business/member roles sees only the current business and mode. Removed staff cannot retain access through an old session.
- Public registration works from desktop and a phone browser, including QR scan, copyable UPI information, and paused/unavailable states. No app installation or push permission is involved.
- Cash and UPI confirmation activate once. Reference reuse, rejected proof, delayed PT verification, final-slot concurrency, appointments, renewal, cancellation and external-refund records behave correctly. Reconcile report totals to verified rows and refunds; unconfirmed receipts refunded externally are shown separately.
- Published plans, approved AI drafts, goal history, photos, analysis and PDFs are accessible only to the linked member and authorized staff. AI drafts and goal notes remain private. Expired gym PT retains published history while new uploads require active PT and membership; inactive relationships lose all access.
- Inbox read state survives reload. Retried events and announcements do not duplicate messages. Audience targeting excludes inactive/other-business relationships. Expiry reminders stop when paid coverage is extended.
- Verify actual ACS delivery for verification, recovery, staff/client invitation, payment confirmation, membership expiry and billing notices. Inspect failure/retry behavior with `scripts/email_outbox.py`; do not infer delivery from queued status.
- Verify Razorpay test and then live merchant/subscription behavior: signed webhooks, first actual payment, authorization-only, failed renewal, duplicates/out-of-order events, missed-event reconciliation, cancellation and recovery. A real charge requires an appropriate test/pilot payer; this work has not charged anyone.
- Exercise provider outages and recovery. Support can diagnose pending manual verification, PT resolution, failed outbox rows and billing reconciliation with the existing operator tools.

## Rollback and monitoring

Pause new gym/PT purchases from Reports if rollout exposes a problem. This does not cancel purchases, delete records, revoke entitlements or prevent admins resolving received money. Continue processing necessary email and billing events. Observe API errors, worker failures, oldest pending email, failed delivery counts, pending billing reconciliation and unresolved PT receipts.

Roll back application images/web assets to captured immutable versions if needed. Keep additive migrations applied; never delete financial history or roll back schema by removing columns/tables. V12 remains compatible with previous business-notice writers. Once V13 client invitations have been issued, the previous application cannot consume those client claims safely; use a forward fix or revoke pending client invitations before reverting identity code. A database restore is a separate recovery operation with explicit reconciliation of payments/events received since the backup.

## Outstanding external release gates

- Refresh Azure interactive authentication and identify/verify separate staging targets and their settings.
- Rehearse migration/restore against a suitable copy of the actual target database.
- Deploy and verify API, web, analysis/email/billing workers and reminder schedule.
- Record actual ACS and Razorpay verification and the two-gym/one-coach pilot.
- Monitor production release. None of these gates is marked complete by local fixture tests.

## Deferred form analysis

`FORM_ANALYSIS_ENABLED` is the central server setting, defaulting to `false`.
Set it consistently on the API and analysis worker (locally in `local.settings.json`
Values, or in deployed environment variables). Only `true` enables the feature.
The web app loads `/features` before rendering, with a five-second timeout and a
safe disabled fallback; no separate Vite flag or frontend rebuild is required.
Restart API/worker processes and reload open browser sessions after changing it.

While disabled, analysis navigation, dashboard metrics, client/member uploads,
results, PDFs and promotional text are hidden. Analysis API and legacy jobs/frame
routes return 404, and the worker exits without receiving queue messages. Inbox
queries exclude historical analysis notifications from both the list and unread
count. Other coaching plans, progress photos and gym features remain available.
Existing records, blobs, and queued messages are preserved; queues still follow
their configured message expiry. Stop any running analysis execution before the
release switch if immediate cessation is required. Decommission/scale down an
existing analysis worker deployment separately to avoid idle compute costs.
