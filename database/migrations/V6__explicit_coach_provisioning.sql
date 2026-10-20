-- A staff profile is not an independent business registration.
-- Signup explicitly calls ensure_coach_business in the application transaction.
DROP TRIGGER provision_new_coach_business ON coaches;

ALTER TABLE form_analyses ADD CONSTRAINT form_analyses_organization_identity UNIQUE(organization_id,id);
CREATE TABLE form_analysis_assets (
    blob_name TEXT PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    analysis_id TEXT NOT NULL,
    FOREIGN KEY(organization_id,analysis_id) REFERENCES form_analyses(organization_id,id)
);
-- Only unambiguous stored references are adopted. Duplicate names are retained
-- in results but cannot authorize a download until explicitly reconciled.
WITH media_refs AS (
    SELECT DISTINCT id, organization_id,
        split_part(substr(value #>> '{}', 9), '?', 1) AS blob_name
    FROM form_analyses,
        LATERAL jsonb_path_query(result_json, '$.**.image_path') AS value
    WHERE jsonb_typeof(value)='string'
        AND (value #>> '{}') LIKE '/frames/%'
)
INSERT INTO form_analysis_assets(blob_name,organization_id,analysis_id)
SELECT blob_name,min(organization_id),min(id) FROM media_refs
GROUP BY blob_name HAVING count(*)=1 AND min(organization_id) IS NOT NULL;
