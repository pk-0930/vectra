# Step 1 — organization foundations, slice 1

Status: implemented and verified; the user authorized continuation with the remaining Step 1 slices. Slice 2 is now covered by [the backfill review](GYM_MANAGEMENT_STEP_1_BACKFILL_REVIEW.md). Step 1 is not complete. Scope follows the accepted [Step 0 review](GYM_MANAGEMENT_STEP_0_REVIEW.md) and [implementation plan](GYM_MANAGEMENT_IMPLEMENTATION_PLAN.md). No deployment or existing database modification is part of this slice.

## What changes

`database/migrations/V3__organization_foundations.sql` adds the structures needed to identify businesses and their people. V1 and V2 remain unchanged. Existing API and UI behavior is unchanged.

| Structure | Purpose |
| --- | --- |
| `organizations` | Separate gym/coaching businesses; lifecycle status and a legacy billing-transition marker. |
| `organization_relationships` | One relationship per personal user per business. A user may belong to several businesses. |
| `organization_staff_roles` | Independently grant/revoke owner, admin and trainer roles. Retain revoked rows; allow re-granting without erasing history. |
| `legacy_coach_organizations` | Unique coach-to-business mapping for the next backfill slice. Initially empty. |
| `clients.organization_id` | Business context for an existing client record, nullable during expansion. |
| `clients.organization_relationship_id` | Optional verified account claim through that business relationship. Initially null; no claims inferred. |
| `trainer_client_assignments` | Separate coaching assignment history; one current assignment for each trainer/client pair. |

The existing `clients` table represents the conceptual client/member profile from Step 0; creating a second profile table would duplicate existing coaching history. Its legacy `coach_id` remains required until a separately reviewed compatibility/cutover change. New fields stay nullable so the current application's inserts work. The actual repository adapter is exercised by the upgrade test.

Composite foreign keys reject roles, client claims and assignments referencing a relationship/client in another business. A relationship can claim at most one client in that business; multiple unclaimed clients remain valid. Unique partial indexes prevent concurrent duplicate current roles/assignments and allow historical revoked/ended rows. Foreign keys restrict deletion of referenced new business records rather than cascading away membership/assignment history.

`billing_transition=legacy_access` is reserved for the next slice's verified legacy mapping. Its default is `none`; neither value is a paid entitlement or a subscription implementation. Migration V3 does not populate organizations, map coaches, activate memberships or change authorization.

## Deliberate boundaries

- This is additive schema expansion, not finished tenant isolation. Current endpoints still use coach ownership. Existing child tables, jobs and media are not yet business-scoped.
- The database enforces structural same-business references. Assignment eligibility, current-role checks, immediate session revocation, last-owner protection and membership/PT eligibility are later transactional service rules. An assignment must never be treated as sufficient authorization.
- No fixed 10-client counting implementation, single-trainer-per-client rule, commercial terms or membership calendar behavior is introduced here.
- Staff removal must revoke a staff role, preserving an independent client relationship. Disabling the whole relationship is reserved for removing all business access. Account deletion has new referential restrictions once new records are populated; deletion/retention policy must be reviewed before exposing deletion operations.
- `updated_at` is initially defaulted only; future repositories must update it on mutations. There is no runtime schema creation or hidden trigger-based backfill.

## Verification

Run from the repository root with Docker running and backend dependencies installed:

```bash
VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python \
  -m unittest discover -s database/tests -v
```

The suite creates a randomly named Docker network and PostgreSQL 16 container with temporary in-memory storage, a random test password, and an ephemeral localhost port. It mounts only the migration directory read-only into the same Flyway 13.0.0 image used by the existing workflow. It never reads `.env`, local settings, `flyway.conf`, Azure credentials, or an external database URL. It removes its own container/network through unittest cleanup. If the process is forcibly killed, inspect `vectra-schema-test-*` resources and remove only the matching disposable resources; never prune shared Docker volumes.

Coverage includes:

- Fresh V1→V2→V3 migration, validation and repeat migration with unchanged history.
- Versioned V2→V3 upgrade with synthetic records in all ten existing tables.
- Populated unversioned V1 schema adopted through Flyway baseline, then V2→V3.
- Exact preservation of existing row data, IDs, JSON, timestamps and media/PDF references. New client fields remain null. Includes duplicate client names, shared descriptive gym labels and ownerless jobs/analyses.
- Actual old repository client creation/read and rejection of another coach's client ID after V3.
- Same-business foreign keys, uniqueness, nullable claim safeguards, valid role/type/date values, role revocation preserving member/other-business relationships, assignment history and concurrent duplicate role grants.

The opt-in suite lives under `database/tests` so ordinary backend unit tests remain independent of Docker. PostgreSQL SQL execution alone would not be reported as Flyway verification; this suite actually invokes Flyway.

Backend regression command:

```bash
cd mobility-ai-service
venv/bin/python -m unittest discover -s tests
```

Results on 17 October 2026: all 11 PostgreSQL/Flyway integration tests passed (14.469 seconds), and all 32 existing backend tests passed. The first rehearsals exposed a missing required field in the synthetic fixture and duplicate baseline options in the test runner; both were corrected before the passing run. The migration itself passed its initial fresh-install and structural checks. The already-declared `psycopg[binary]` dependency was missing locally and was installed into the existing backend virtual environment; no requirements changes were needed.

Frontend lint/build is not applicable because no UI files changed. Live Azure schema drift, production lock duration, production-volume performance and existing-data anomalies are not tested by a synthetic local rehearsal.

## Rollout and rollback notes

1. Review this slice before proceeding. Do not push/merge it to `main` as a way to preview it: the existing `database/**` workflow runs migrations on main pushes. This work does not alter that workflow or run it remotely.
2. Before any deployment, inspect the target schema and Flyway history, verify no competing V3 has been added, and take a database backup plus schema export. Rehearse on an isolated restored copy; the fixtures here do not replace that gate. If V3 is taken before this migration is deployed anywhere, choose the next unused version; never edit an already applied migration.
3. V3 is transactional additive DDL. Adding constraints/indexes takes locks on `clients`; measure duration on the restored copy, configure an appropriate migration lock timeout, and schedule the rollout accordingly. Stop and investigate on validation or lock failure.
4. Verify Flyway history/checksums, unchanged existing row counts, null expansion fields and old application smoke tests. New tenant-facing features remain disabled/unimplemented.
5. Application rollback keeps V3 in place: the existing adapter still works with the expanded schema. Do not run `clean`, delete Flyway history, drop new columns/tables or rewrite V1/V2. If a deployed database recovery is required, use the reviewed backup/restore procedure and account for writes since the backup; future schema correction should be a new forward migration.

## Next review checkpoint

After approval of this slice, proceed to Step 1 slice 2: deterministic one-coaching-business-per-coach backfill, owner relationships/roles, preserved legacy access, client scoping and assignment mapping, and an explicit exception report for ownerless/inconsistent records. Reconcile on an isolated copy. Existing writes during the transition need a deliberate compatibility/catch-up strategy before switching reads.

Slice 3 then introduces scoped repositories/constraints. Step 2 authentication and UI changes remain outside Step 1. No full Step 1 completion or production-readiness claim is made by this slice.
