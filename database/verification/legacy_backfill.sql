-- Read-only post-V4 report. Run only against the explicitly selected rehearsal
-- database first. No credentials, migrations, catch-up or automatic repairs here.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

SELECT
    (SELECT count(*) FROM coaches) AS coaches,
    (SELECT count(*) FROM legacy_coach_organizations) AS mapped_coaches,
    (SELECT count(*) FROM clients) AS clients,
    (SELECT count(*) FROM clients WHERE organization_id IS NOT NULL) AS scoped_clients,
    (SELECT count(*) FROM clients WHERE organization_relationship_id IS NOT NULL) AS claimed_clients,
    (SELECT count(*) FROM trainer_client_assignments WHERE ended_at IS NULL) AS current_assignments,
    (SELECT count(*) FROM legacy_ownership_issues) AS unresolved_issues;

-- Retained child data: compare counts and identifiers with the pre-migration
-- snapshot/backup as well; counts alone cannot prove ownership or integrity.
SELECT 'client_goals' AS record_type, count(*) AS records FROM client_goals
UNION ALL SELECT 'client_progress_photos', count(*) FROM client_progress_photos
UNION ALL SELECT 'nutrition_plans', count(*) FROM nutrition_plans
UNION ALL SELECT 'workout_plans', count(*) FROM workout_plans
UNION ALL SELECT 'ai_plan_drafts', count(*) FROM ai_plan_drafts
UNION ALL SELECT 'form_analyses', count(*) FROM form_analyses
UNION ALL SELECT 'legacy_jobs', count(*) FROM legacy_job_ownership_issues;

SELECT issue_code, count(*) AS records
FROM legacy_ownership_issues GROUP BY issue_code ORDER BY issue_code;

SELECT issue_code, entity_type, entity_id, expected_organization_id, observed_organization_id
FROM legacy_ownership_issues ORDER BY issue_code, entity_type, entity_id;

COMMIT;
