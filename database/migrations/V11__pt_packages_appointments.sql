CREATE TABLE pt_purchase_states (
 purchase_id UUID PRIMARY KEY,
 organization_id BIGINT NOT NULL,
 member_relationship_id BIGINT NOT NULL,
 trainer_relationship_id BIGINT NOT NULL,
 reserved_until TIMESTAMPTZ NOT NULL,
 resolution_reason TEXT,
 FOREIGN KEY(organization_id,purchase_id) REFERENCES gym_pending_purchases(organization_id,id),
 FOREIGN KEY(organization_id,member_relationship_id) REFERENCES organization_relationships(organization_id,id),
 FOREIGN KEY(organization_id,trainer_relationship_id) REFERENCES organization_relationships(organization_id,id)
);
CREATE TABLE pt_entitlements (
 purchase_id UUID PRIMARY KEY,
 organization_id BIGINT NOT NULL,
 member_relationship_id BIGINT NOT NULL,
 trainer_relationship_id BIGINT NOT NULL,
 client_id BIGINT NOT NULL,
 starts_on DATE NOT NULL,
 ends_before DATE NOT NULL CHECK(ends_before>starts_on),
 remaining_sessions INTEGER CHECK(remaining_sessions>=0),
 revoked_at TIMESTAMPTZ,
 service_terms JSONB NOT NULL,
 UNIQUE(organization_id,purchase_id),
 FOREIGN KEY(organization_id,purchase_id) REFERENCES gym_pending_purchases(organization_id,id),
 FOREIGN KEY(organization_id,member_relationship_id) REFERENCES organization_relationships(organization_id,id),
 FOREIGN KEY(organization_id,trainer_relationship_id) REFERENCES organization_relationships(organization_id,id),
 FOREIGN KEY(organization_id,client_id) REFERENCES clients(organization_id,id)
);
CREATE INDEX pt_capacity_idx ON pt_entitlements(organization_id,trainer_relationship_id,ends_before);
CREATE TABLE coaching_appointments (
 id UUID PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id),
 request_id UUID NOT NULL,
 created_by BIGINT NOT NULL REFERENCES users(id),
 entitlement_id UUID,
 client_id BIGINT NOT NULL,
 trainer_relationship_id BIGINT NOT NULL,
 starts_at TIMESTAMPTZ NOT NULL,
 ends_at TIMESTAMPTZ NOT NULL CHECK(ends_at>starts_at),
 status TEXT NOT NULL DEFAULT 'booked' CHECK(status IN ('booked','cancelled','completed')),
 version INTEGER NOT NULL DEFAULT 1,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(organization_id,created_by,request_id),
 UNIQUE(organization_id,id),
 FOREIGN KEY(organization_id,entitlement_id) REFERENCES pt_entitlements(organization_id,purchase_id),
 FOREIGN KEY(organization_id,client_id) REFERENCES clients(organization_id,id),
 FOREIGN KEY(organization_id,trainer_relationship_id) REFERENCES organization_relationships(organization_id,id)
);
CREATE INDEX coaching_appointment_overlap_idx ON coaching_appointments(organization_id,trainer_relationship_id,starts_at) WHERE status<>'cancelled';
CREATE TABLE pt_audit (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id),
 actor_user_id BIGINT NOT NULL REFERENCES users(id),
 purchase_id UUID,
 appointment_id UUID,
 action TEXT NOT NULL,
 details JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 FOREIGN KEY(organization_id,purchase_id) REFERENCES gym_pending_purchases(organization_id,id),
 FOREIGN KEY(organization_id,appointment_id) REFERENCES coaching_appointments(organization_id,id)
);
CREATE TRIGGER pt_audit_immutable BEFORE UPDATE OR DELETE ON pt_audit FOR EACH ROW EXECUTE FUNCTION protect_gym_payment_history();

-- Revocation is durable: re-granting a role does not silently restore old PT work.
ALTER TABLE pt_entitlements ADD COLUMN requires_reassignment BOOLEAN NOT NULL DEFAULT false;
CREATE FUNCTION revoke_pt_work() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_org BIGINT; target_relationship BIGINT;
BEGIN
    target_org := NEW.organization_id;
    IF TG_TABLE_NAME='organization_staff_roles' THEN
        target_relationship := NEW.relationship_id;
        IF NEW.revoked_at IS NULL OR OLD.revoked_at IS NOT NULL THEN RETURN NEW; END IF;
        IF EXISTS(SELECT 1 FROM organization_staff_roles WHERE organization_id=target_org
            AND relationship_id=target_relationship AND revoked_at IS NULL) THEN RETURN NEW; END IF;
    ELSE
        target_relationship := NEW.id;
        IF NEW.status<>'inactive' OR OLD.status='inactive' THEN RETURN NEW; END IF;
    END IF;
    UPDATE pt_entitlements SET requires_reassignment=true
        WHERE organization_id=target_org AND trainer_relationship_id=target_relationship AND revoked_at IS NULL;
    UPDATE coaching_appointments SET status='cancelled',version=version+1
        WHERE organization_id=target_org AND trainer_relationship_id=target_relationship AND status='booked';
    UPDATE trainer_client_assignments SET ended_at=now()
        WHERE organization_id=target_org AND trainer_relationship_id=target_relationship AND ended_at IS NULL;
    RETURN NEW;
END $$;
CREATE TRIGGER trainer_role_pt_revocation AFTER UPDATE OF revoked_at ON organization_staff_roles
    FOR EACH ROW EXECUTE FUNCTION revoke_pt_work();
CREATE TRIGGER trainer_relationship_pt_revocation AFTER UPDATE OF status ON organization_relationships
    FOR EACH ROW EXECUTE FUNCTION revoke_pt_work();
