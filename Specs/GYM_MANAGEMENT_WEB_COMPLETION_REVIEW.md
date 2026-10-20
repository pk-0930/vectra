# Web implementation — Step 8 and Step 10 preparation

Implemented on 2026-10-20 under the instruction to complete the remaining web work without interim reviews. Existing working-tree changes were preserved. React Native and all mobile push work remain deferred. This report does not claim a live release.

## Member coaching access

- The existing member workspace continues to use plan, PDF, photo, goal and movement-analysis services. Added a goal-history view and explicit upload eligibility.
- Existing saved workout/nutrition plans are published content; approving an AI draft creates a published plan. AI drafts and private goal notes remain staff-only. Publishing a plan creates a member inbox notification in the same transaction.
- An active business relationship retains published plans and progress history after gym/PT package expiry. New member uploads require an active client profile plus current paid membership and usable PT coverage. Revoked or unassigned PT work does not enable uploads. Independent coaching has no gym-membership gate. The API checks eligibility before blob upload and again at record creation; current entitlement rows are locked during the request.
- Admins can invite an existing unlinked coaching profile through Business access → Coaching client. The expiring, single-use invitation proves recipient control and supports new or existing accounts. Acceptance rechecks the inviter's permission, locks the exact profile, rejects conflicting links, and grants no staff role. No name-based automatic linking occurs.

## Owner reports and rollout control

Reports show confirmed cash/UPI receipts, full external refunds, active/expiring members and PT purchase states/values. Receipt dates and refund-record dates are India-local; membership counts are current as of the reported date. Aggregates cover all matching rows, independently of existing bounded workspace lists. Date ranges are limited to 367 inclusive days.

Refunds of never-confirmed receipts appear separately from refunds of verified collections. Net verified collections subtract only the latter. Pending purchases are never treated as collected money. These reports do not claim accounting revenue recognition, bank balance or automated reconciliation.

Only owners may pause new gym/PT purchases. The control is audited and serialized with purchase creation. Existing records, paid entitlements and receipt/refund resolution remain available. Trainer/member requests cannot acquire financial or rollout permissions through the UI or forged API requests.

## Persistent web inbox

Inbox entries carry business, recipient relationship, event identity and read timestamp. Reads and updates are scoped to the current recipient and active business access. Cursor pagination and unread counts are supported.

- Existing durable payment/refund, membership expiry, trainer reassignment and billing notices are mirrored transactionally into the inbox. V12 backfills prior business notices for matching active relationships. Authentication/recovery tokens are never copied.
- New published plans and completed movement analyses create inbox notices.
- Admin announcements target all active relationships, trainers, gym members/registrants, or linked active coaching clients. Server-selected audience snapshots stay within the business. Request IDs serialize retries and reject conflicting content.
- Email delivery remains independent. Inbox content persists if ACS delivery fails. No push provider, device registration or native app is required.

## Schema and release tooling

- V12: inbox, announcement records, event triggers, purchase rollout setting and immutable rollout audit.
- V13: verified client invitations, exact profile foreign key and client-role validation. `client` is an invitation purpose, never an organization staff role.
- `/health/ready`: bounded database/schema readiness check; failures return a generic 503 without connection details.
- `scripts/web_release_check.py`: environment-only configuration checks, provider-mode separation and optional read-only schema/outbox metadata.
- `scripts/deploy_web_containers.py`: explicit target and immutable-SHA deployment plan, optional execution for pre-provisioned API/analysis/email/billing containers and reminder job. It does not create cloud resources, change secrets or migrate databases.
- `validate-web.yml`: PR/manual frontend, backend and isolated PostgreSQL checks. Static Web App deployment remains main-push-only.
- `.dockerignore`: prevents local settings, environment files, virtual environments and generated outputs from entering release images.

See [WEB_RELEASE_RUNBOOK.md](WEB_RELEASE_RUNBOOK.md) for target setup, provider checks, pilot scenarios, release order, monitoring and rollback. V13 must precede the updated API. Keep additive schema on application rollback; handle pending client invitations explicitly before reverting identity code.

## Verification

- Backend unittest suite: **90 tests passed** (`/tmp/vectra-web-backend-final.log`).
- Final full isolated database regression: **121 tests passed** (`/tmp/vectra-web-database-final.log`), including the final invitation, HTTP authorization and entitlement-locking changes.
- Focused web database/HTTP acceptance: **9 tests passed** (`/tmp/vectra-web-db-final.log`), including concurrent announcements, scoped read state, report/refund reconciliation, paused purchases, private goal notes/drafts, expired history, client invitations, HTTP permissions and migration backup/restore. Counts overlap; do not add them.
- Frontend `npm run lint` and `npm run build` passed. `git diff --check` passed.
- Browser verification used synthetic users and a disposable PostgreSQL database with provider integrations mocked. Owner report totals rendered correctly; announcement delivery reached four synthetic inboxes; marking read reduced unread count. A member could load coaching and inbox pages with no admin composer, including a 390-pixel phone-browser viewport.
- Screenshots are local review artifacts: `/tmp/vectra-web-reports.png`, `/tmp/vectra-web-inbox.png`, `/tmp/vectra-web-member-phone.png`. They are not committed media and do not contain production data.
- The backup/restore test creates V11 fixture data, upgrades through latest migrations, checks notification backfill and compatibility with existing notice writers, dumps/restores into another disposable database and validates Flyway plus preserved records.

Reproduce from the repository root:

```sh
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python -m unittest discover -s database/tests -v
cd mobility-ai-service
venv/bin/python -m unittest discover -s tests -v
cd ../vectra-ui
npm run lint
npm run build
```

## Remaining external work

Step 8 is implemented locally. Step 10 has release tooling and local rehearsal evidence, but is not complete end to end. Azure resource discovery failed because interactive authentication expired (AADSTS700082). Target staging/production configuration, a target-database restore rehearsal, deployed worker/schedule verification, real ACS delivery, Razorpay live verification, the two-gym/one-online-coach real-user pilot and monitored production release remain outstanding.

No live payment, real email, production migration or production deployment was performed. Mobile work is not a dependency for any of the remaining web release gates.
