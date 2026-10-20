-- Post-V5 read-only reconciliation. Use only an explicitly selected database.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT
    (SELECT count(*) FROM coaches) AS coaches,
    (SELECT count(*) FROM legacy_coach_organizations) AS mapped_coaches,
    (SELECT count(*) FROM clients WHERE organization_id IS NULL) AS unscoped_clients,
    (SELECT count(*) FROM quarantined_coaching_records) AS quarantined_records,
    (SELECT count(*) FROM legacy_job_ownership_issues) AS retained_legacy_jobs;
SELECT record_type, count(*) AS records FROM quarantined_coaching_records
GROUP BY record_type ORDER BY record_type;
SELECT * FROM quarantined_coaching_records ORDER BY record_type,record_id;
SELECT * FROM legacy_ownership_issues ORDER BY issue_code,entity_type,entity_id;
COMMIT;
