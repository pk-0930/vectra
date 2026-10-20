-- Step 1, slice 2. Flyway executes this migration in one transaction.
-- Freeze participating writes during the snapshot; never rely on a name match.
-- Abort rather than wait indefinitely on a busy database. Rehearse lock duration
-- on a restored copy before deployment. Existing application writes resume after
-- commit and are visible in legacy_ownership_issues until the cutover catch-up.
SET LOCAL lock_timeout = '5s';
LOCK TABLE coaches, clients, organizations, organization_relationships,
    organization_staff_roles, legacy_coach_organizations, trainer_client_assignments
    IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE
    source_coach RECORD;
    new_organization_id BIGINT;
    owner_relationship_id BIGINT;
BEGIN
    -- Do not overwrite a pre-existing mapping, revive a revoked owner, or
    -- convert a gym/paid business into a legacy coaching business.
    IF EXISTS (
        SELECT 1
        FROM legacy_coach_organizations mapping
        JOIN coaches coach ON coach.id = mapping.coach_id
        JOIN organizations organization ON organization.id = mapping.organization_id
        WHERE organization.organization_type <> 'coaching'
            OR organization.status <> 'active'
            OR organization.billing_transition <> 'legacy_access'
            OR NOT EXISTS (
                SELECT 1
                FROM organization_relationships relationship
                JOIN organization_staff_roles role
                    ON role.organization_id = relationship.organization_id
                    AND role.relationship_id = relationship.id
                WHERE relationship.organization_id = mapping.organization_id
                    AND relationship.user_id = coach.user_id
                    AND relationship.status = 'active'
                    AND role.role = 'owner' AND role.revoked_at IS NULL
            )
    ) THEN
        RAISE EXCEPTION 'Legacy mapping conflicts with its business or owner; review before backfill';
    END IF;

    -- A scoped client without its coach's matching map needs explicit review.
    IF EXISTS (
        SELECT 1 FROM clients client
        LEFT JOIN legacy_coach_organizations mapping ON mapping.coach_id = client.coach_id
        WHERE client.organization_id IS NOT NULL
            AND client.organization_id IS DISTINCT FROM mapping.organization_id
    ) THEN
        RAISE EXCEPTION 'Existing client business conflicts with legacy coach mapping; review before backfill';
    END IF;

    FOR source_coach IN
        SELECT coach.id, coach.user_id
        FROM coaches coach
        WHERE NOT EXISTS (
            SELECT 1 FROM legacy_coach_organizations mapping WHERE mapping.coach_id = coach.id
        )
        ORDER BY coach.id
    LOOP
        INSERT INTO organizations (name, organization_type, billing_transition)
        VALUES ('Coaching business ' || source_coach.id, 'coaching', 'legacy_access')
        RETURNING id INTO new_organization_id;

        INSERT INTO legacy_coach_organizations (coach_id, organization_id)
        VALUES (source_coach.id, new_organization_id);

        INSERT INTO organization_relationships (organization_id, user_id)
        VALUES (new_organization_id, source_coach.user_id)
        RETURNING id INTO owner_relationship_id;

        INSERT INTO organization_staff_roles (organization_id, relationship_id, role)
        VALUES (new_organization_id, owner_relationship_id, 'owner');
    END LOOP;
END
$$;

-- Preserve personal data, login claims, is_active and all original timestamps.
UPDATE clients client
SET organization_id = mapping.organization_id
FROM legacy_coach_organizations mapping
WHERE mapping.coach_id = client.coach_id AND client.organization_id IS NULL;

-- Only active legacy clients get current assignments. An ended assignment is
-- evidence of an intentional change: do not recreate it, report the gap below.
INSERT INTO trainer_client_assignments (organization_id, trainer_relationship_id, client_id)
SELECT client.organization_id, relationship.id, client.id
FROM clients client
JOIN coaches coach ON coach.id = client.coach_id
JOIN organization_relationships relationship
    ON relationship.organization_id = client.organization_id
    AND relationship.user_id = coach.user_id
WHERE client.is_active AND NOT EXISTS (
    SELECT 1 FROM trainer_client_assignments assignment
    WHERE assignment.organization_id = client.organization_id
        AND assignment.trainer_relationship_id = relationship.id
        AND assignment.client_id = client.id
);

-- Operational review only; do not expose this view through public/member APIs.
-- Live view deliberately catches old-version writes arriving AFTER this migration.
-- Empty results are necessary but not sufficient for tenant cutover: descendants,
-- queue messages, blob inventory and all authorization paths still need review.
-- Like V2, support an adopted database without the optional legacy jobs table.
DO $$
BEGIN
    IF to_regclass('public.jobs') IS NOT NULL THEN
        EXECUTE 'CREATE VIEW legacy_job_ownership_issues AS SELECT id::TEXT AS entity_id FROM jobs';
    ELSE
        EXECUTE 'CREATE VIEW legacy_job_ownership_issues AS SELECT NULL::TEXT AS entity_id WHERE false';
    END IF;
END
$$;

CREATE VIEW legacy_ownership_issues AS
SELECT 'coach_mapping_missing'::TEXT AS issue_code, 'coach'::TEXT AS entity_type,
    coach.id::TEXT AS entity_id, NULL::BIGINT AS expected_organization_id,
    NULL::BIGINT AS observed_organization_id
FROM coaches coach
LEFT JOIN legacy_coach_organizations mapping ON mapping.coach_id = coach.id
WHERE mapping.coach_id IS NULL
UNION ALL
SELECT 'legacy_business_invalid', 'coach', mapping.coach_id::TEXT,
    mapping.organization_id, mapping.organization_id
FROM legacy_coach_organizations mapping
JOIN organizations organization ON organization.id = mapping.organization_id
WHERE organization.organization_type <> 'coaching'
    OR organization.status <> 'active' OR organization.billing_transition <> 'legacy_access'
UNION ALL
SELECT 'legacy_owner_missing', 'coach', coach.id::TEXT,
    mapping.organization_id, mapping.organization_id
FROM coaches coach
JOIN legacy_coach_organizations mapping ON mapping.coach_id = coach.id
WHERE NOT EXISTS (
    SELECT 1 FROM organization_relationships relationship
    JOIN organization_staff_roles role
        ON role.organization_id = relationship.organization_id AND role.relationship_id = relationship.id
    WHERE relationship.organization_id = mapping.organization_id
        AND relationship.user_id = coach.user_id AND relationship.status = 'active'
        AND role.role = 'owner' AND role.revoked_at IS NULL
)
UNION ALL
SELECT CASE WHEN client.organization_id IS NULL THEN 'client_scope_missing'
    ELSE 'client_scope_conflict' END, 'client', client.id::TEXT,
    mapping.organization_id, client.organization_id
FROM clients client
LEFT JOIN legacy_coach_organizations mapping ON mapping.coach_id = client.coach_id
WHERE client.organization_id IS NULL
    OR client.organization_id IS DISTINCT FROM mapping.organization_id
UNION ALL
SELECT 'client_assignment_missing', 'client', client.id::TEXT,
    client.organization_id, client.organization_id
FROM clients client
JOIN coaches coach ON coach.id = client.coach_id
WHERE client.is_active AND client.organization_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM trainer_client_assignments assignment
    JOIN organization_relationships relationship
        ON relationship.organization_id = assignment.organization_id
        AND relationship.id = assignment.trainer_relationship_id
    WHERE assignment.organization_id = client.organization_id AND assignment.client_id = client.id
        AND relationship.user_id = coach.user_id AND relationship.status = 'active'
        AND assignment.ended_at IS NULL
)
UNION ALL
SELECT 'inactive_client_has_current_assignment', 'client', client.id::TEXT,
    client.organization_id, assignment.organization_id
FROM clients client
JOIN trainer_client_assignments assignment ON assignment.client_id = client.id
WHERE NOT client.is_active AND assignment.ended_at IS NULL
UNION ALL
SELECT 'analysis_owner_unresolved', 'form_analysis', analysis.id,
    NULL::BIGINT, client.organization_id
FROM form_analyses analysis
LEFT JOIN clients client ON client.id = analysis.client_id
WHERE client.organization_id IS NULL
UNION ALL
-- Jobs have no coach/client ownership column. An ID shared with an analysis
-- alone is insufficient evidence to assign a business; retain for explicit review.
SELECT 'legacy_job_requires_review', 'job', job.entity_id, NULL::BIGINT, NULL::BIGINT
FROM legacy_job_ownership_issues job
UNION ALL
SELECT 'nutrition_author_conflict', 'nutrition_plan', plan.id::TEXT,
    client.organization_id, author.organization_id
FROM nutrition_plans plan
JOIN clients client ON client.id = plan.client_id
LEFT JOIN legacy_coach_organizations author ON author.coach_id = plan.created_by_coach_id
WHERE client.organization_id IS NULL OR author.organization_id IS DISTINCT FROM client.organization_id
UNION ALL
SELECT 'workout_author_conflict', 'workout_plan', plan.id::TEXT,
    client.organization_id, author.organization_id
FROM workout_plans plan
JOIN clients client ON client.id = plan.client_id
LEFT JOIN legacy_coach_organizations author ON author.coach_id = plan.created_by_coach_id
WHERE client.organization_id IS NULL OR author.organization_id IS DISTINCT FROM client.organization_id
UNION ALL
SELECT 'draft_author_conflict', 'ai_plan_draft', draft.id::TEXT,
    client.organization_id, author.organization_id
FROM ai_plan_drafts draft
JOIN clients client ON client.id = draft.client_id
LEFT JOIN legacy_coach_organizations author ON author.coach_id = draft.coach_id
WHERE client.organization_id IS NULL OR author.organization_id IS DISTINCT FROM client.organization_id;
