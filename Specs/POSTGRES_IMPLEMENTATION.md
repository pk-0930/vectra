# Postgres Implementation

## Overview

### Current Implementation

We are currently using sqllite for persistence which is not scalable and is not production ready. So, we are going to switch to Azure Database for PostgreSQL Flexible Server.

### After Implementation

After this postgres implementation, the data that is getting persisted in sqllite will be going to be in postgres going forward. We are not migrating the data that is in sqllite to postgres.


## Postgres Details

Azure Database for PostgreSQL Flexible Server. (Configured in a minimal way considering cost)

Resource Group - "rg-vectra"
Server Name - "psql-vectra"
DB name - "Vectra"
Administrator Login - "vectraadmin"
Password - "admin@123"
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

### Security and Access

- UI should not have direct access to the DB, every data must be fetched through backend api
- Use `sslmode = "require"` if needed. Because TLS/SSL is enforeced on server by default for Azure Database for Postgres server.

### Not Considered

- KeyVault



