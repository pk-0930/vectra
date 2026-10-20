# Step 1 — repository scoping and transition handling, slice 3

Status: implemented and locally verified; the user approved proceeding to Step 2 slice 1. The user approved proceeding to this slice. See the [backfill review](GYM_MANAGEMENT_STEP_1_BACKFILL_REVIEW.md) and [implementation plan](GYM_MANAGEMENT_IMPLEMENTATION_PLAN.md). No existing application database or production deployment was touched.

## Changes

V5 is an additive forward migration; V1–V4 remain unchanged. It takes a write lock on the participating tables, catches up coaches and clients written after V4, makes client business context required, and adds business context and same-client/same-business foreign keys to goals, progress photos, nutrition/workout plans, AI drafts and form analyses. Original record IDs, profile fields, JSON, media references and historical timestamps remain unchanged.

Consistent descendants inherit their client's business. Ownerless analyses, conflicting plan/draft authorship and invalid approved-plan references remain in the database with null business context. This is an explicit quarantine marker, not a guessed ownership assignment. `quarantined_coaching_records` exposes their type/ID for operational review. Legacy jobs remain in their original table and remain explicitly unresolved; a job ID alone is not proof of ownership.

The new `OrganizationRepository` requires a positive business ID for each instance and offers scoped client, descendant, photo-reference and analysis-claim operations. It uses explicit business predicates for reads and updates, verifies client scope inside the write transaction, parameterizes values, allowlists table/field names, and disallows caller-supplied ownership changes. It is available through `PostgresPlatformRepository.for_organization(...)`; instances do not share a mutable selected business.

The organization repository is the data boundary that Step 2 will bind to authorized relationships. Passing an organization ID is not proof that the caller belongs to it. Current service signatures remain coach-based; broad owner/admin/PT/member access and the new shell are not enabled by this slice.

Current coach-facing repositories also change:

- Plan/draft/analysis reads and updates skip quarantined records.
- Analyses with no client are no longer visible to every coach. The old `client_id IS NULL OR coach_id = ...` condition is removed, also fixing its client-filter precedence bug.
- Plan table names are restricted to nutrition and workout tables.
- The unused concrete `PostgresJobRepository` now fails explicitly on construction. Current API and worker paths already use `form_analyses`; `/jobs` compatibility routes still delegate to those current paths. The old adapter cannot accidentally restore global access to unresolved legacy jobs. In-memory queue test adapters remain supported.

## Compatibility writes and constraints

Compatibility triggers are introduced explicitly in this slice, replacing V4's snapshot-only transition window. They are versioned Flyway DDL, not runtime schema creation:

| Operation | Behavior |
| --- | --- |
| Existing unmapped coach at V5 | Create one mapped coaching business with `legacy_access`, relationship and owner role. |
| New coach inserted after V5 | Create one mapped coaching business with billing marker `none`; do not invent paid access or grandfather new registrations. |
| Existing mapping | Reuse it; do not re-grant revoked roles, reactivate relationships or reset billing state. |
| Old client insert without business ID | Derive business from its coach's mapping; require a same-business coach relationship. |
| Active new client | Create a same-business assignment if the coach has a current staff role; unique constraints suppress duplicate role-derived insert candidates. |
| Client ownership update | Reject changes to business or legacy coach identity; future trainer reassignment belongs in assignment records. |
| Descendant insert without business ID | Derive scope from its client, then validate author and approved-plan references. |
| New ownerless/cross-business descendant | Reject it. |
| Existing descendant ownership change | Reject changes to client/business once scoped. |

Database checks establish structural membership, not live staff authorization. Role/status changes are Step 2 authorization work. Client activation/deactivation is not silently interpreted as trainer reactivation/removal; the operational report still surfaces assignment lifecycle inconsistencies for review.

The coach-insert compatibility trigger represents the current independent-coach signup flow. Step 2 must replace or explicitly adapt this behavior before adding staff coach profiles: creating a gym trainer's profile must not accidentally create an independent business. Do not expose new staff-account flows on this compatibility behavior alone.

No automatic repair of quarantine is exposed. A future reviewed repair needs evidence, audited decisions and a constrained transaction; current normal repository operations cannot select quarantined rows. Administrative SQL can inspect retained records. Blob contents and external queue messages are not moved or rewritten by V5.

## Verification

From the repository root:

```bash
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python \
  -m unittest discover -s database/tests -v
```

From `mobility-ai-service/`:

```bash
venv/bin/python -m unittest discover -s tests
```

The PostgreSQL/Flyway harness uses disposable storage, generated credentials and no external database settings. Historical V3/V4 tests intentionally allow later pending migrations during their historical validation. V5 tests use strict validation.

New database scenarios cover:

- V4-to-V5 catch-up after late writes and exact preservation of original record fields.
- Fresh install through V5 and repeated Flyway execution.
- Restore of a synthetic V4 dump, then migration to V5.
- Positive and cross-business negative client/descendant CRUD and photo-reference reads.
- Quarantined records excluded from current legacy and scoped repositories.
- Real old-adapter coach/client/plan creation after V5, including automatic scope and assignment.
- Direct SQL rejection of forged scope, client moves and cross-business authorship.
- Approved-plan reference checks and preserved revoked owners.
- Concurrent scoped analysis claims, with exactly one successful claim.

Unit tests cover invalid business context, separate repository instances, immutable context, rejected table/ownership fields and the retired legacy adapter. Existing coaching/AI/queue/squat regressions are retained. Verification on 17 October 2026 passed: **34 PostgreSQL/Flyway integration tests** (123.576 seconds), **36 backend unit tests**, Python syntax checks on the seven relevant repository/test files, and `git diff --check`. No UI files changed, so frontend lint/build does not apply.

The read-only `database/verification/organization_scoping.sql` reports mapping gaps, null client scope, quarantined records and remaining operational issues. Zero quarantine rows is not required to preserve legacy data, but every retained unresolved category must stay restricted and receive an operational disposition. No unresolved record is automatically made visible to a business.

## Verification boundary and Step 2 prerequisites

This slice completes the local database/repository foundation, not the entire permission system. Existing coach checks remain in service/API paths. Trusted internal legacy methods still use global analysis IDs; their access must not be exposed as tenant authorization. Step 2 must use the authorized business-bound repository and recheck current relationship/role status on every protected operation.

Step 2 must also carry business context through queues and retry/poison handling, protect photo/frame/download endpoints, address query-string tokens and development-secret fallback, clear business-scoped browser state, and implement owner/admin/PT/member behavior. The current `/frames` route is not made authenticated by a repository filter; no claim of complete media isolation is made here. Database quarantine does not revoke previously distributed media URLs or secure external storage by itself.

No live Azure schema, actual user-data copy, blob inventory, queue backlog, provider connection, production-scale lock duration or deployed application was tested. The restored-copy rehearsal uses synthetic data. A real isolated restored copy and security rehearsal remain deployment gates.

## Rollout and rollback

1. Review this slice before starting Step 2. No push, merge or deployment has occurred. Main pushes touching database files can run the existing migration workflow.
2. Verify target schema/history and unused V5 version; take and test a backup/schema export. Rehearse on a real restored copy and inspect both operational reports.
3. Deploy V5 before this repository code. The new code requires the descendant scope columns; it is not compatible with a pre-V5 database. Coordinate a maintenance window for schema/application switch and worker restart, especially to prevent old readers from exposing quarantined rows during the transition.
4. V5 takes write locks with a five-second lock acquisition timeout. Its catch-up and trigger installation commit atomically, closing the missing-scope write window. Measure actual runtime and storage/index cost on the real copy; do not assume small-fixture timing predicts production.
5. On failed migration, stop and investigate; PostgreSQL rolls back the transaction. Do not use Flyway clean/history deletion or checksum repair to bypass a data conflict.
6. Schema rollback is forward-only by default. Existing writes remain compatible with the expanded schema. However, reverting to code before this slice restores the old globally visible ownerless-analysis query: retain quarantine filtering/legacy-adapter restrictions in any rollback build or keep affected endpoints unavailable. Do not call an unrestricted previous release a safe access rollback.
7. Database restore is a separate recovery decision accounting for writes since backup. Preserve mappings/history and use forward corrections after a successful migration.

Next review checkpoint: Step 1 slice 3, then Step 2 accounts and permissions in its own bounded slices. Production readiness and actual legacy exception disposition remain open.
