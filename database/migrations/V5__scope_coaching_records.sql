-- Step 1 slice 3: catch up the old writer under a write lock, then install
-- explicit compatibility triggers. No ownership is inferred from media names.
SET LOCAL lock_timeout = '5s';
LOCK TABLE coaches, clients, organizations, organization_relationships,
    organization_staff_roles, legacy_coach_organizations, trainer_client_assignments,
    client_goals, client_progress_photos, nutrition_plans, workout_plans,
    ai_plan_drafts, form_analyses IN SHARE ROW EXCLUSIVE MODE;

CREATE FUNCTION ensure_coach_business(source_coach_id BIGINT, legacy BOOLEAN)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
    account_id BIGINT;
    business_id BIGINT;
    relationship_id BIGINT;
BEGIN
    SELECT user_id INTO STRICT account_id FROM coaches WHERE id = source_coach_id FOR UPDATE;
    SELECT organization_id INTO business_id FROM legacy_coach_organizations WHERE coach_id = source_coach_id;
    IF business_id IS NOT NULL THEN
        -- Never restore a revoked owner or reset billing/status on an existing map.
        RETURN business_id;
    END IF;
    INSERT INTO organizations(name, organization_type, billing_transition)
    VALUES ('Coaching business ' || source_coach_id, 'coaching',
        CASE WHEN legacy THEN 'legacy_access' ELSE 'none' END) RETURNING id INTO business_id;
    INSERT INTO legacy_coach_organizations(coach_id, organization_id) VALUES(source_coach_id, business_id);
    INSERT INTO organization_relationships(organization_id, user_id)
    VALUES(business_id, account_id) RETURNING id INTO relationship_id;
    INSERT INTO organization_staff_roles(organization_id, relationship_id, role)
    VALUES(business_id, relationship_id, 'owner');
    RETURN business_id;
END
$$;

DO $$
DECLARE source_id BIGINT;
BEGIN
    FOR source_id IN SELECT id FROM coaches ORDER BY id LOOP
        PERFORM ensure_coach_business(source_id, true);
    END LOOP;
    IF EXISTS (
        SELECT 1 FROM clients c JOIN legacy_coach_organizations m ON m.coach_id=c.coach_id
        WHERE c.organization_id IS NOT NULL AND c.organization_id <> m.organization_id
    ) THEN
        RAISE EXCEPTION 'Conflicting client scope requires review before cutover';
    END IF;
END
$$;
UPDATE clients c SET organization_id=m.organization_id
FROM legacy_coach_organizations m WHERE m.coach_id=c.coach_id AND c.organization_id IS NULL;
ALTER TABLE clients ALTER COLUMN organization_id SET NOT NULL;

INSERT INTO trainer_client_assignments(organization_id, trainer_relationship_id, client_id)
SELECT c.organization_id,r.id,c.id FROM clients c
JOIN coaches coach ON coach.id=c.coach_id
JOIN organization_relationships r ON r.organization_id=c.organization_id AND r.user_id=coach.user_id
JOIN organization_staff_roles role ON role.organization_id=r.organization_id AND role.relationship_id=r.id
WHERE c.is_active AND r.status='active' AND role.role='owner' AND role.revoked_at IS NULL
    AND NOT EXISTS (SELECT 1 FROM trainer_client_assignments a
        WHERE a.organization_id=c.organization_id AND a.trainer_relationship_id=r.id AND a.client_id=c.id);

CREATE FUNCTION provision_new_coach_business() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    PERFORM ensure_coach_business(NEW.id, false);
    RETURN NEW;
END
$$;
CREATE TRIGGER provision_new_coach_business AFTER INSERT ON coaches
FOR EACH ROW EXECUTE FUNCTION provision_new_coach_business();

CREATE FUNCTION scope_legacy_client() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='UPDATE' AND (NEW.organization_id IS DISTINCT FROM OLD.organization_id
        OR NEW.coach_id IS DISTINCT FROM OLD.coach_id) THEN
        RAISE EXCEPTION 'Client ownership is immutable; use reviewed reassignment procedures';
    END IF;
    IF NEW.organization_id IS NULL THEN
        SELECT organization_id INTO NEW.organization_id FROM legacy_coach_organizations WHERE coach_id=NEW.coach_id;
    END IF;
    IF NEW.organization_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM coaches coach JOIN organization_relationships r ON r.user_id=coach.user_id
        WHERE coach.id=NEW.coach_id AND r.organization_id=NEW.organization_id
    ) THEN
        RAISE EXCEPTION 'Client coach does not belong to this organization';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER scope_legacy_client BEFORE INSERT OR UPDATE ON clients
FOR EACH ROW EXECUTE FUNCTION scope_legacy_client();

CREATE FUNCTION assign_new_legacy_client() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.is_active THEN
        INSERT INTO trainer_client_assignments(organization_id,trainer_relationship_id,client_id)
        SELECT NEW.organization_id,r.id,NEW.id FROM coaches coach
        JOIN organization_relationships r ON r.user_id=coach.user_id AND r.organization_id=NEW.organization_id
        JOIN organization_staff_roles role ON role.organization_id=r.organization_id AND role.relationship_id=r.id
        WHERE coach.id=NEW.coach_id AND r.status='active' AND role.role IN ('owner','admin','trainer')
            AND role.revoked_at IS NULL
        ON CONFLICT (organization_id,trainer_relationship_id,client_id) WHERE ended_at IS NULL DO NOTHING;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER assign_new_legacy_client AFTER INSERT ON clients
FOR EACH ROW EXECUTE FUNCTION assign_new_legacy_client();

-- NULL scope is a quarantine marker for retained unresolved legacy records.
-- Compatibility triggers reject new unresolved records; existing quarantined
-- rows must be reconciled explicitly before they can be edited or processed.
DO $$
DECLARE table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['client_goals','client_progress_photos','nutrition_plans',
        'workout_plans','ai_plan_drafts','form_analyses'] LOOP
        EXECUTE format('ALTER TABLE %I ADD COLUMN organization_id BIGINT NULL REFERENCES organizations(id)', table_name);
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY(organization_id,client_id) REFERENCES clients(organization_id,id)',
            table_name,table_name || '_client_organization_fk');
        EXECUTE format('CREATE INDEX %I ON %I(organization_id,client_id)', table_name || '_organization_idx',table_name);
    END LOOP;
END
$$;
UPDATE client_goals t SET organization_id=c.organization_id FROM clients c WHERE c.id=t.client_id;
UPDATE client_progress_photos t SET organization_id=c.organization_id FROM clients c WHERE c.id=t.client_id;
UPDATE form_analyses t SET organization_id=c.organization_id FROM clients c WHERE c.id=t.client_id;
UPDATE nutrition_plans t SET organization_id=c.organization_id FROM clients c, legacy_coach_organizations m
WHERE c.id=t.client_id AND m.coach_id=t.created_by_coach_id AND m.organization_id=c.organization_id;
UPDATE workout_plans t SET organization_id=c.organization_id FROM clients c, legacy_coach_organizations m
WHERE c.id=t.client_id AND m.coach_id=t.created_by_coach_id AND m.organization_id=c.organization_id;
UPDATE ai_plan_drafts t SET organization_id=c.organization_id FROM clients c, legacy_coach_organizations m
WHERE c.id=t.client_id AND m.coach_id=t.coach_id AND m.organization_id=c.organization_id
AND (t.approved_plan_id IS NULL OR
    (t.plan_kind='nutrition' AND EXISTS (SELECT 1 FROM nutrition_plans p WHERE p.id=t.approved_plan_id
        AND p.client_id=t.client_id AND p.organization_id=c.organization_id)) OR
    (t.plan_kind='workout' AND EXISTS (SELECT 1 FROM workout_plans p WHERE p.id=t.approved_plan_id
        AND p.client_id=t.client_id AND p.organization_id=c.organization_id)));

CREATE FUNCTION scope_coaching_record() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    client_organization BIGINT;
    author_coach BIGINT;
    valid_plan BOOLEAN;
BEGIN
    SELECT organization_id INTO client_organization FROM clients WHERE id=NEW.client_id;
    IF client_organization IS NULL THEN
        RAISE EXCEPTION 'A scoped client is required';
    END IF;
    IF TG_OP='UPDATE' AND (NEW.client_id IS DISTINCT FROM OLD.client_id OR
        (OLD.organization_id IS NOT NULL AND NEW.organization_id IS DISTINCT FROM OLD.organization_id)) THEN
        RAISE EXCEPTION 'Coaching record ownership is immutable';
    END IF;
    IF NEW.organization_id IS NULL THEN NEW.organization_id=client_organization; END IF;
    IF NEW.organization_id <> client_organization THEN RAISE EXCEPTION 'Cross-organization record'; END IF;
    IF TG_TABLE_NAME IN ('nutrition_plans','workout_plans') THEN
        author_coach=NEW.created_by_coach_id;
    ELSIF TG_TABLE_NAME='ai_plan_drafts' THEN
        author_coach=NEW.coach_id;
    END IF;
    IF author_coach IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM coaches coach JOIN organization_relationships r ON r.user_id=coach.user_id
        WHERE coach.id=author_coach AND r.organization_id=NEW.organization_id
    ) THEN RAISE EXCEPTION 'Author belongs to another organization'; END IF;
    IF TG_TABLE_NAME='ai_plan_drafts' THEN
        IF NEW.approved_plan_id IS NOT NULL THEN
            IF NEW.plan_kind NOT IN ('nutrition','workout') THEN RAISE EXCEPTION 'Invalid plan kind'; END IF;
            EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I WHERE id=$1 AND client_id=$2 AND organization_id=$3)',
                CASE NEW.plan_kind WHEN 'nutrition' THEN 'nutrition_plans' ELSE 'workout_plans' END)
                INTO valid_plan USING NEW.approved_plan_id,NEW.client_id,NEW.organization_id;
            IF NOT valid_plan THEN RAISE EXCEPTION 'Approved plan does not belong to this client'; END IF;
        END IF;
    END IF;
    RETURN NEW;
END
$$;
DO $$
DECLARE table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['client_goals','client_progress_photos','nutrition_plans',
        'workout_plans','ai_plan_drafts','form_analyses'] LOOP
        EXECUTE format('CREATE TRIGGER scope_coaching_record BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION scope_coaching_record()',table_name);
    END LOOP;
END
$$;

CREATE VIEW quarantined_coaching_records AS
SELECT 'form_analyses'::TEXT AS record_type,id::TEXT AS record_id FROM form_analyses WHERE organization_id IS NULL
UNION ALL SELECT 'nutrition_plans',id::TEXT FROM nutrition_plans WHERE organization_id IS NULL
UNION ALL SELECT 'workout_plans',id::TEXT FROM workout_plans WHERE organization_id IS NULL
UNION ALL SELECT 'ai_plan_drafts',id::TEXT FROM ai_plan_drafts WHERE organization_id IS NULL;
-- The legacy jobs table remains unscoped and is NOT a tenant-accessible source.
