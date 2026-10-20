-- Additive web delivery: no mobile device or push-provider dependency.
CREATE TABLE notification_inbox (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL,
 relationship_id BIGINT NOT NULL,
 event_key TEXT NOT NULL,
 subject TEXT NOT NULL CHECK(length(subject) BETWEEN 1 AND 160),
 message TEXT NOT NULL CHECK(length(message) BETWEEN 1 AND 4000),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 read_at TIMESTAMPTZ,
 UNIQUE(organization_id,relationship_id,event_key),
 FOREIGN KEY(organization_id,relationship_id) REFERENCES organization_relationships(organization_id,id)
);
CREATE INDEX notification_inbox_recipient_idx ON notification_inbox(organization_id,relationship_id,id DESC);
CREATE TABLE business_announcements (
 id UUID NOT NULL,
 organization_id BIGINT NOT NULL REFERENCES organizations(id),
 sender_user_id BIGINT NOT NULL REFERENCES users(id),
 audience TEXT NOT NULL CHECK(audience IN ('all','trainers','members','clients')),
 subject TEXT NOT NULL,
 message TEXT NOT NULL,
 recipient_count INTEGER NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id)
);
-- Mirror durable business notices in the same transaction as the source event.
-- Verification/recovery/invitation tokens never enter the inbox.
CREATE FUNCTION inbox_business_notice() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO notification_inbox(organization_id,relationship_id,event_key,subject,message)
 SELECT NEW.organization_id,r.id,'notice:'||NEW.event_key,NEW.subject,NEW.message
 FROM organization_relationships r JOIN users u ON u.id=r.user_id
 WHERE r.organization_id=NEW.organization_id AND lower(u.email)=lower(NEW.recipient) AND r.status='active'
 ON CONFLICT DO NOTHING;
 RETURN NEW;
END $$;
CREATE TRIGGER billing_notice_inbox AFTER INSERT ON billing_notifications
 FOR EACH ROW EXECUTE FUNCTION inbox_business_notice();
INSERT INTO notification_inbox(organization_id,relationship_id,event_key,subject,message,created_at)
 SELECT n.organization_id,r.id,'notice:'||n.event_key,n.subject,n.message,n.created_at
 FROM billing_notifications n JOIN users u ON lower(u.email)=lower(n.recipient)
 JOIN organization_relationships r ON r.user_id=u.id AND r.organization_id=n.organization_id
 WHERE r.status='active' ON CONFLICT DO NOTHING;
CREATE TABLE business_web_rollout (
 organization_id BIGINT PRIMARY KEY REFERENCES organizations(id),
 purchases_enabled BOOLEAN NOT NULL DEFAULT true,
 updated_by BIGINT REFERENCES users(id),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE business_web_rollout_audit (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id),
 actor_user_id BIGINT NOT NULL REFERENCES users(id),
 purchases_enabled BOOLEAN NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TRIGGER web_rollout_audit_immutable BEFORE UPDATE OR DELETE ON business_web_rollout_audit
 FOR EACH ROW EXECUTE FUNCTION protect_gym_payment_history();

CREATE FUNCTION inbox_analysis_completed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status='completed' AND OLD.status IS DISTINCT FROM NEW.status THEN
  INSERT INTO notification_inbox(organization_id,relationship_id,event_key,subject,message)
  SELECT NEW.organization_id,c.organization_relationship_id,'analysis:'||NEW.id,
   'Your movement analysis is ready','Open your member workspace to view the completed movement report.'
  FROM clients c JOIN organization_relationships r ON r.organization_id=c.organization_id AND r.id=c.organization_relationship_id
  WHERE c.organization_id=NEW.organization_id AND c.id=NEW.client_id AND r.status='active'
  ON CONFLICT DO NOTHING;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER analysis_completed_inbox AFTER UPDATE OF status ON form_analyses
 FOR EACH ROW EXECUTE FUNCTION inbox_analysis_completed();
