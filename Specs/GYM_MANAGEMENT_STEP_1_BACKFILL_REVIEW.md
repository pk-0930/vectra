# Step 1 — legacy backfill, slice 2

Status: implemented and locally verified; awaiting user review before slice 3. The user approved completing the remaining Step 1 slices before Step 2, with review checkpoints. This follows the [schema review](GYM_MANAGEMENT_STEP_1_SCHEMA_REVIEW.md). No production or existing local application database is changed by this development work.

## Behavior

`database/migrations/V4__backfill_legacy_coaching_organizations.sql` adds a one-time, transactional backfill. V1, V2 and V3 are unchanged.

- Every unmapped existing coach receives one independent coaching business, an active relationship for their existing personal account, and an owner role. The durable `legacy_coach_organizations` mapping—not a gym label or person's name—establishes identity. Processing is ordered by coach ID; generated organization IDs are not assumed to equal coach IDs.
- Initial names are `Coaching business <coach ID>`. Names are editable display labels for later settings work, not business identifiers. Two coaches with the same `associated_gym` text stay separate.
- New mapped businesses carry `billing_transition=legacy_access`. This records the accepted transition direction without implementing billing checks or granting a paid membership. Existing application access remains unchanged.
- Existing clients receive their coach's mapped `organization_id`. Their IDs, coach ownership, profile data, login-claim fields, active status and timestamps are preserved. No automatic account claim or name-based merge occurs.
- Active clients get current assignments to the owner-coach. Inactive clients are scoped but receive no new current assignment. An existing ended assignment is not revived; the report flags the gap for review. Assignment timestamps record the migration, not an invented historical coaching start date.
- Existing valid mappings are reused. An incompatible pre-existing business, revoked/missing owner, or conflicting client scope aborts the migration instead of silently transferring data or restoring access. Corrections require evidence and review before retrying.

The backfill does not rewrite goals, plans, drafts, photos, analysis records, legacy jobs, JSON or blob/PDF references. Their ownership is still derived through existing client relationships where possible; direct descendant/job scoping and application enforcement belong to slice 3 and Step 2.

## Exceptions and the transition window

The read-only `legacy_ownership_issues` view reports:

| Issue | Required response before cutover |
| --- | --- |
| Missing coach map or client scope | Catch up records created by the old application, preserving IDs. |
| Conflicting client scope or invalid legacy business | Investigate source ownership; never move data by guessing. |
| Missing current owner/assignment | Review intentional revocation/reassignment; never automatically re-grant access. |
| Inactive client with a current assignment | Review lifecycle inconsistency without silently changing history. |
| Analysis with no scoped client | Establish ownership from evidence or explicitly restrict/quarantine it. |
| Legacy job | Explicit ownership review: a shared ID alone does not prove business ownership. |
| Nutrition/workout/draft author conflicts | Resolve disagreement between author and client business before tenant access. |

`legacy_job_ownership_issues` supports the optional legacy `jobs` table. Adopted databases without that table remain supported, matching V2's compatibility behavior. All existing jobs are conservatively reported, even when an analysis has a matching ID. A job copied by V2 may appear both as an unresolved analysis and a legacy job; these are separate source records, not duplicate assignments.

These views are operational reports, not public/member APIs or authorization filters. They do not themselves quarantine rows or close existing legacy access paths. No new tenant-facing feature is enabled. A blob/queue inventory still requires separate reconciliation; database references do not prove that stored media or queue messages are correctly scoped.

Participating tables are locked during V4's transaction, with a five-second lock wait limit. Old application writes resume after commit. New coaches/clients can therefore remain unmapped, and the live report makes that visible. Running Flyway again does not rerun V4 or automatically repair these rows. It also does not reactivate roles revoked since migration.

Before switching reads, slice 3 must establish scoped writes and an explicit, reviewed catch-up operation under a write pause or equivalent consistency boundary. Then reconcile again and resolve/restrict exceptions. Do not use this snapshot backfill alone to claim tenant isolation or zero-downtime migration readiness.

## Verification and reproduction

From the repository root:

```bash
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python \
  -m unittest discover -s database/tests -v
```

The harness uses generated credentials, disposable PostgreSQL 16 storage and the repository's Flyway 13.0.0 image. It never reads application settings or an external database URL. Temporary containers/networks are removed after the run. The foundation tests remain pinned to V3, explicitly allowing later pending migrations only in their historical validation checks. V4 validation is strict.

New scenarios cover fresh installation through V4; populated V3 upgrade; unversioned V1 adoption through V4; exact preservation of all original row fields except the intended client scope; shared names/gym labels; inactive clients; existing valid mappings and ended assignments; revoked owner rejection; author conflicts; late writes; optional absent jobs table; repeat Flyway runs; lock timeout and retry; atomic conflict rejection and correction; and the read-only report.

The restore test actually runs `pg_dump` on a synthetic V3 database, restores that dump into another isolated database, applies V4, and exercises existing repository reads and writes. This is a synthetic restore rehearsal, not a copy of the user's production database.

Read-only post-migration reconciliation is provided in `database/verification/legacy_backfill.sql`. Against an explicitly selected rehearsal database, run it with `psql --set=ON_ERROR_STOP=1 --file=database/verification/legacy_backfill.sql` using your normal connection configuration. The file prints coach/client/mapping/assignment counts, retained child-table counts, and grouped/detailed issues in one read-only snapshot. It contains no credentials or repairs. Compare against the pre-migration snapshot; counts alone are insufficient.

Results on 17 October 2026: all 23 PostgreSQL/Flyway integration tests passed in 71.840 seconds (12 backfill scenarios plus 11 foundation regressions). All 32 backend unit tests passed. The first combined run found that the older V3-only validation checks rejected the now-pending V4; those historical checks were adjusted as described above, and the full suite then passed. Python syntax, whitespace and `git diff --check` checks passed. Backend regression used `venv/bin/python -m unittest discover -s tests` from `mobility-ai-service/`. No UI changes were made, so frontend checks do not apply.

## Rollout, rollback and next checkpoint

1. Review this slice before slice 3. No push, merge, workflow dispatch or deployment has been performed. A main push touching `database/**` still triggers the existing migration workflow.
2. Before production review, inspect schema drift and Flyway history, confirm V4 is unused, take a database backup/schema export, and restore a real database copy into an isolated environment. Do not rewrite migrations already applied elsewhere.
3. Rehearse V4 and the report on that copy. Measure lock duration and transaction size; the small fixtures do not establish production-volume performance. A lock timeout or ownership conflict must leave the transaction rolled back; investigate and retry after resolving the cause, without deleting Flyway history or using `repair` to bypass a failed data check.
4. Keep the existing application version available for rollback. It still reads/writes through coach ownership; the expanded schema and mapping data can remain. Review any deletion workflow before rollout: new assignment/mapping references deliberately restrict deletion of referenced records.
5. Do not drop mappings, columns, assignment history or exception views to roll back application code. Database restoration is a separate reviewed recovery action that must account for writes since the backup; corrections after successful deployment should use forward migrations.
6. Next is Step 1 slice 3: scoped repositories, descendant/job ownership, write compatibility/catch-up and cutover constraints. Step 2 accounts/permissions/UI remains pending until Step 1's remaining acceptance checks pass.
