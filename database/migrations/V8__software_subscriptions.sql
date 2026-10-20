-- Preserve all pre-billing organizations. A transition deadline is an explicit operator action.
ALTER TABLE organizations ADD COLUMN billing_required BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN billing_legacy_until TIMESTAMPTZ;
ALTER TABLE organizations ALTER COLUMN billing_required SET DEFAULT true;
CREATE TABLE business_onboarding_requests (
    user_id BIGINT NOT NULL REFERENCES users(id),
    request_id UUID NOT NULL,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    business_type TEXT NOT NULL CHECK(business_type IN ('gym','coaching')),
    PRIMARY KEY(user_id,request_id)
);
CREATE TABLE software_subscriptions (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    requested_by BIGINT NOT NULL REFERENCES users(id),
    mode TEXT NOT NULL CHECK(mode IN ('test','live')),
    plan_snapshot JSONB NOT NULL,
    terms_version TEXT NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    provider_id TEXT,
    customer_id TEXT,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN
        ('queued','creating','creation_unknown','creation_failed','created','authenticated',
         'active','pending','halted','paused','cancelled','completed','expired')),
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    cancel_confirmed BOOLEAN NOT NULL DEFAULT false,
    start_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_sync_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_token UUID,
    lease_until TIMESTAMPTZ,
    failures INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    UNIQUE(mode,provider_id),
    UNIQUE(organization_id,id)
);
CREATE UNIQUE INDEX software_subscription_open ON software_subscriptions(organization_id,mode) WHERE closed_at IS NULL;
CREATE INDEX software_subscription_sync ON software_subscriptions(next_sync_at);
CREATE TABLE software_payments (
    mode TEXT NOT NULL CHECK(mode IN ('test','live')),
    payment_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    organization_id BIGINT NOT NULL,
    subscription_id UUID NOT NULL,
    amount_paise BIGINT NOT NULL CHECK(amount_paise>0),
    refunded_paise BIGINT NOT NULL DEFAULT 0 CHECK(refunded_paise>=0 AND refunded_paise<=amount_paise),
    currency TEXT NOT NULL CHECK(currency='INR'),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL CHECK(period_end>period_start),
    paid_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(mode,payment_id),
    UNIQUE(mode,invoice_id),
    FOREIGN KEY(organization_id,subscription_id) REFERENCES software_subscriptions(organization_id,id)
);
CREATE INDEX software_payment_coverage ON software_payments(organization_id,mode,period_end);
-- Store only verified event metadata, not provider payloads containing payment instruments/contact data.
CREATE TABLE software_webhook_events (
    mode TEXT NOT NULL,
    event_id TEXT NOT NULL,
    body_hash TEXT NOT NULL,
    event_type TEXT NOT NULL,
    provider_subscription_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processed','ignored')),
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    PRIMARY KEY(mode,event_id)
);
CREATE TABLE billing_notifications (
    id UUID PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    recipient TEXT NOT NULL,
    event_key TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(organization_id,recipient,event_key)
);
ALTER TABLE email_outbox ALTER COLUMN action_id DROP NOT NULL;
ALTER TABLE email_outbox ADD COLUMN billing_notification_id UUID UNIQUE REFERENCES billing_notifications(id),
    ADD CONSTRAINT email_outbox_one_source CHECK(num_nonnulls(action_id,billing_notification_id)=1);
CREATE TABLE billing_operator_audit (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    operation TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
