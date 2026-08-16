# Postgres Implementation

## Overview

### Current Implementation

The backend uses Azure Database for PostgreSQL Flexible Server through repository
classes and `psycopg`. The current schema was historically created by idempotent
`CREATE TABLE IF NOT EXISTS` statements in the repositories.

### After Implementation

Flyway is the source of truth for PostgreSQL schema changes. The existing Azure
database is adopted at baseline version 1, while new local databases create the
current schema from `database/migrations/V1__baseline.sql`.

The legacy `jobs` table remains in the baseline. Migration V2 moves any legacy
rows into `form_analyses` using the same conflict-safe behavior previously run by
the application at startup. PostgreSQL repositories no longer create or migrate
tables during service initialization.

SQLite data is not migrated to PostgreSQL.


## Postgres Details

Azure Database for PostgreSQL Flexible Server. (Configured in a minimal way considering cost)

Resource Group - "rg-vectra"
Server Name - "psql-vectra"
DB name - "Vectra"
Administrator Login - "vectraadmin"
Password - configured outside the repository through deployment secrets
Endpoint - "psql-vectra.postgres.database.azure.com"


## Technical Considerations

### Principles and Patterns

- Follow SOLID principles
- Implement Repository design pattern for database access
- Connection string can be stored in a config file for now and will be moved to keyvault in future
- Maintain clear seperation of concerns with Controller-Service-Repository (CSR) layout with below considerations,
    - `routers/` or `api/`: Contains the "controllers" (path operations) that handle HTTP concerns.
    - `services/`: Contains the business logic and rules.
    - `repositories/`: Handles database interactions (CRUD)
    - `schemas/`: Contains Pydantic models for request and response validation.
- Keep `app.py` thin

### Flyway Workflow

- Local migrations use `database/flyway.conf`, copied from
  `database/flyway.conf.example`; the populated file is ignored by Git.
- GitHub Actions uses repository secrets `FLYWAY_URL`, `FLYWAY_USER`, and
  `FLYWAY_PASSWORD`.
- Flyway is run before the backend API and worker images are built and published.
- Existing Azure tables are adopted using `baselineOnMigrate=true` and
  `baselineVersion=1`.
- Future schema changes must be new immutable versioned migrations.
- The GitHub runner must have network access to Azure PostgreSQL.

### Security and Access

- UI should not have direct access to the DB, every data must be fetched through backend api
- Use `sslmode = "require"` if needed. Because TLS/SSL is enforeced on server by default for Azure Database for Postgres server.

### Not Considered

- KeyVault
