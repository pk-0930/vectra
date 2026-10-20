-- Step 1, slice 1: expand only. Existing coach-owned reads/writes remain valid.
-- Legacy mapping/backfill and repository cutover are separate reviewed slices.

CREATE TABLE organizations (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(btrim(name)) > 0),
    organization_type TEXT NOT NULL CHECK (organization_type IN ('gym', 'coaching')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    -- A migration transition marker, NOT a paid subscription entitlement.
    billing_transition TEXT NOT NULL DEFAULT 'none'
        CHECK (billing_transition IN ('none', 'legacy_access')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE organization_relationships (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, user_id),
    UNIQUE (organization_id, id)
);

CREATE INDEX organization_relationships_user_idx
    ON organization_relationships (user_id, organization_id);

-- Roles are independent of the client link and any future paid membership.
-- Revoke a trainer role rather than disabling the entire relationship when
-- the same person must retain member access in that business.
CREATE TABLE organization_staff_roles (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    relationship_id BIGINT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'trainer')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ NULL,
    CHECK (revoked_at IS NULL OR revoked_at >= granted_at),
    FOREIGN KEY (organization_id, relationship_id)
        REFERENCES organization_relationships (organization_id, id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX organization_staff_roles_current_idx
    ON organization_staff_roles (organization_id, relationship_id, role)
    WHERE revoked_at IS NULL;

CREATE INDEX organization_staff_roles_relationship_idx
    ON organization_staff_roles (organization_id, relationship_id);

-- Filled by the next slice, with one deterministic organization per coach.
-- A dedicated mapping avoids inferring ownership from names/associated_gym.
CREATE TABLE legacy_coach_organizations (
    coach_id BIGINT PRIMARY KEY REFERENCES coaches(id) ON DELETE RESTRICT,
    organization_id BIGINT NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE RESTRICT,
    mapped_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Nullable during expansion so the current application can continue inserting
-- clients. No inferred login claims, data moves or access changes occur here.
ALTER TABLE clients
    ADD COLUMN organization_id BIGINT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    ADD COLUMN organization_relationship_id BIGINT NULL,
    ADD CONSTRAINT clients_claim_requires_organization
        CHECK (organization_relationship_id IS NULL OR organization_id IS NOT NULL),
    ADD CONSTRAINT clients_organization_identity UNIQUE (organization_id, id),
    ADD CONSTRAINT clients_organization_claim UNIQUE (organization_id, organization_relationship_id),
    ADD CONSTRAINT clients_relationship_same_organization
        FOREIGN KEY (organization_id, organization_relationship_id)
        REFERENCES organization_relationships (organization_id, id) ON DELETE RESTRICT;

CREATE TABLE trainer_client_assignments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    trainer_relationship_id BIGINT NOT NULL,
    client_id BIGINT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ NULL,
    CHECK (ended_at IS NULL OR ended_at >= started_at),
    FOREIGN KEY (organization_id, trainer_relationship_id)
        REFERENCES organization_relationships (organization_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (organization_id, client_id)
        REFERENCES clients (organization_id, id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX trainer_client_assignments_current_idx
    ON trainer_client_assignments (organization_id, trainer_relationship_id, client_id)
    WHERE ended_at IS NULL;

CREATE INDEX trainer_client_assignments_client_idx
    ON trainer_client_assignments (organization_id, client_id);

-- Current roles, last-owner protection, paid eligibility and capacity are
-- service/transaction rules for later slices. An assignment alone grants no
-- permission. Do not enable tenant-facing routes on this schema alone.
