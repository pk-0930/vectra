-- Registration is an identity relationship and a pending purchase, never an entitlement.
CREATE TABLE gym_profiles (
    organization_id BIGINT PRIMARY KEY REFERENCES organizations(id),
    public_id UUID NOT NULL UNIQUE,
    revision INTEGER NOT NULL DEFAULT 0 CHECK (revision >= 0),
    configuration JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE gym_assets (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES gym_profiles(organization_id),
    kind TEXT NOT NULL CHECK (kind IN ('logo','payment_qr')),
    png BYTEA NOT NULL CHECK (octet_length(png) <= 2097152),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX gym_assets_organization_idx ON gym_assets(organization_id);
CREATE TABLE gym_setup_audit (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES gym_profiles(organization_id),
    revision INTEGER NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    configuration JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id,revision)
);
CREATE TABLE gym_pending_purchases (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES gym_profiles(organization_id),
    relationship_id BIGINT NOT NULL,
    request_id UUID NOT NULL,
    request_hash TEXT NOT NULL,
    profile_revision INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    amount_paise BIGINT NOT NULL CHECK (amount_paise > 0),
    currency TEXT NOT NULL DEFAULT 'INR' CHECK (currency='INR'),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','superseded')),
    replaces_id UUID REFERENCES gym_pending_purchases(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id,relationship_id,request_id),
    FOREIGN KEY (organization_id,relationship_id) REFERENCES organization_relationships(organization_id,id)
);
CREATE INDEX gym_pending_member_idx ON gym_pending_purchases(organization_id,relationship_id,created_at);
CREATE FUNCTION protect_gym_purchase_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Pending purchase history cannot be deleted'; END IF;
    IF (to_jsonb(NEW)-'status') IS DISTINCT FROM (to_jsonb(OLD)-'status') THEN
        RAISE EXCEPTION 'Purchase snapshots are immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER gym_purchase_immutable BEFORE UPDATE OR DELETE ON gym_pending_purchases
    FOR EACH ROW EXECUTE FUNCTION protect_gym_purchase_snapshot();

-- Verification emails return to the intended public gym even on a different device.
ALTER TABLE identity_actions ADD COLUMN return_gym_public_id UUID REFERENCES gym_profiles(public_id);
