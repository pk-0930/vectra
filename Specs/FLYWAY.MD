# Introduce Flyway Database Migrations

## Summary

Add Flyway as the sole schema-management tool while preserving the existing Azure PostgreSQL schema and data.

Use a versioned `V1` baseline migration with `baselineOnMigrate=true`: empty local databases execute V1, while the existing non-empty Azure database is recorded as version 1 and skips recreating tables.

## Implementation Changes

- Add `database/migrations/V1__baseline.sql`.
  - Reproduce the current tables and constraints from `platform_repository.py` and `job_repository.py`.
  - Preserve the legacy `jobs` table.
  - Include all current tables: users, coaches, clients, goals, progress photos, nutrition plans, workout plans, AI plan drafts, form analyses, and jobs.
  - Use normal Flyway SQL rather than `IF NOT EXISTS`; Flyway controls one-time execution.

- Add `database/migrations/V2__backfill_legacy_jobs.sql`.
  - Move the current `jobs` to `form_analyses` compatibility copy out of runtime Python code.
  - Guard execution when `jobs` does not exist.
  - Use `ON CONFLICT (id) DO NOTHING` so it is safe for the existing Azure data.
  - Azure will baseline at V1, then execute V2.

- Remove runtime schema creation.
  - Delete the PostgreSQL `initialize()` DDL methods and remove calls to them from backend services.
  - Keep the legacy `PostgresJobRepository` and `jobs` table for compatibility.
  - Leave Azure Queue initialization unchanged because it is unrelated to database schema management.

- Add local Flyway configuration documentation:
  - `database/flyway.conf.example` with placeholders such as:
    - `jdbc:postgresql://<POSTGRES_HOST>:<POSTGRES_PORT>/<POSTGRES_DB>?sslmode=disable`
    - `<POSTGRES_USER>`
    - `<POSTGRES_PASSWORD>`
  - Add real local Flyway config files to `.gitignore`.
  - Document Docker-based Flyway commands for the local PostgreSQL container.

- Add `.github/workflows/database-migrations.yml`.
  - Use the pinned official open-source Flyway Docker image.
  - Run on `main` pushes affecting `database/**`, manual dispatch, and `workflow_call`.
  - Run `info`, `validate`, and `migrate`.
  - Configure `baselineOnMigrate=true`, `baselineVersion=1`, `schemas=public`, and a protected migration history table.
  - Read Azure connection details only from GitHub secrets such as `FLYWAY_URL`, `FLYWAY_USER`, and `FLYWAY_PASSWORD`.
  - Do not commit Azure or local credentials.

- Update the backend deployment workflow.
  - Call the reusable migration workflow before building and pushing API/worker images.
  - Make image publishing depend on successful migration completion.
  - This prevents a newly deployed backend from starting before its schema migration has completed.

- Update `README.md` and `Specs/POSTGRES_IMPLEMENTATION.md` with:
  - Flyway directory layout.
  - Local Docker usage.
  - Azure baseline adoption procedure.
  - Required GitHub secrets.
  - The rule that future schema changes must be new immutable `V3`, `V4`, etc. migrations.
  - The requirement that the GitHub runner can reach Azure PostgreSQL; otherwise use a self-hosted runner or private-network integration.

## Test Plan

- Run Flyway against an empty local PostgreSQL container and verify:
  - V1 creates every current table and constraint.
  - V2 completes successfully with no legacy rows.
  - `flyway_schema_history` records both migrations.

- Run against an Azure-like database pre-populated with the current schema and verify:
  - Flyway baselines at version 1.
  - V1 is not re-executed.
  - V2 applies successfully.
  - Existing rows remain intact.

- Seed a legacy `jobs` row and verify V2 copies it into `form_analyses`.

- Run the legacy backfill scenario twice and verify no duplicate form analyses are created.

- Run Flyway `validate` and `info` against the migrated local database.

- Run backend regression tests:

  ```bash
  cd mobility-ai-service
  python -m unittest discover -s tests
  ```

- Confirm the API and worker start successfully after migrations and no longer attempt schema creation during import or service construction.

## Assumptions

- The Azure database contains the same schema represented by the current idempotent SQL.
- The public PostgreSQL schema is `public`.
- The existing `jobs` table is retained for backward compatibility.
- GitHub Actions has network access to Azure PostgreSQL and the required firewall rules are already configured.
- Flyway migrations are applied before backend deployment; migration failures stop image deployment.
