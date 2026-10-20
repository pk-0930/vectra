-- Existing identities retain access without being falsely marked verified.
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ,
    ADD COLUMN verification_required BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ALTER COLUMN verification_required SET DEFAULT true;

CREATE TABLE identity_actions (
    id UUID PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('verify','recover','invite')),
    email TEXT NOT NULL,
    user_id BIGINT REFERENCES users(id),
    organization_id BIGINT REFERENCES organizations(id),
    invited_by BIGINT REFERENCES users(id),
    role TEXT CHECK (role IN ('admin','trainer')),
    token_hash TEXT NOT NULL UNIQUE,
    session_version INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    CHECK (expires_at > created_at),
    CHECK ((kind='invite' AND organization_id IS NOT NULL AND invited_by IS NOT NULL AND role IS NOT NULL)
        OR (kind IN ('verify','recover') AND user_id IS NOT NULL AND organization_id IS NULL AND role IS NULL))
);
CREATE INDEX identity_actions_recipient_idx ON identity_actions(email,kind,created_at);
CREATE TABLE email_outbox (
    id UUID PRIMARY KEY,
    action_id UUID NOT NULL UNIQUE REFERENCES identity_actions(id),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed','cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX email_outbox_pending_idx ON email_outbox(available_at) WHERE status='pending';
CREATE TABLE identity_request_limits (
    bucket_hash TEXT PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    requests INTEGER NOT NULL DEFAULT 1
);
