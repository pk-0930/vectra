ALTER TABLE gym_pending_purchases DROP CONSTRAINT gym_pending_purchases_status_check;
ALTER TABLE gym_pending_purchases ADD CHECK (status IN ('pending','superseded','awaiting_verification','rejected','cancelled','confirmed','refunded'));
ALTER TABLE gym_pending_purchases ADD UNIQUE(organization_id,id);
CREATE TABLE gym_payment_events (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL,
 purchase_id UUID NOT NULL,
 actor_user_id BIGINT NOT NULL REFERENCES users(id),
 kind TEXT NOT NULL CHECK(kind IN ('submitted','evidence','rejected','cancelled','confirmed','correction','refunded')),
 details JSONB NOT NULL,
 evidence BYTEA CHECK(octet_length(evidence)<=2097152),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 FOREIGN KEY(organization_id,purchase_id) REFERENCES gym_pending_purchases(organization_id,id)
);
CREATE TABLE gym_verified_payments (
 purchase_id UUID PRIMARY KEY,
 organization_id BIGINT NOT NULL,
 method TEXT NOT NULL CHECK(method IN ('upi','cash')),
 reference TEXT NOT NULL CHECK(reference<>''),
 amount_paise BIGINT NOT NULL CHECK(amount_paise>0),
 received_on DATE NOT NULL,
 verifier_user_id BIGINT NOT NULL REFERENCES users(id),
 verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(organization_id,reference),
 FOREIGN KEY(organization_id,purchase_id) REFERENCES gym_pending_purchases(organization_id,id)
);
CREATE TABLE gym_membership_periods (
 purchase_id UUID PRIMARY KEY,
 organization_id BIGINT NOT NULL,
 relationship_id BIGINT NOT NULL,
 starts_on DATE NOT NULL,
 ends_before DATE NOT NULL CHECK(ends_before>starts_on),
 revoked_at TIMESTAMPTZ,
 FOREIGN KEY(organization_id,purchase_id) REFERENCES gym_pending_purchases(organization_id,id),
 FOREIGN KEY(organization_id,relationship_id) REFERENCES organization_relationships(organization_id,id)
);
CREATE INDEX gym_membership_coverage_idx ON gym_membership_periods(organization_id,relationship_id,ends_before);
CREATE FUNCTION protect_gym_payment_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Payment history is append-only; record a correction'; END $$;
CREATE TRIGGER gym_event_immutable BEFORE UPDATE OR DELETE ON gym_payment_events FOR EACH ROW EXECUTE FUNCTION protect_gym_payment_history();
CREATE TRIGGER gym_payment_immutable BEFORE UPDATE OR DELETE ON gym_verified_payments FOR EACH ROW EXECUTE FUNCTION protect_gym_payment_history();
