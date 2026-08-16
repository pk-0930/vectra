-- Preserve the runtime jobs-to-form_analyses compatibility copy as a
-- versioned, one-time migration for existing databases.

DO $$
BEGIN
    IF to_regclass('public.jobs') IS NOT NULL THEN
        INSERT INTO form_analyses (
            id,
            client_id,
            analysis_type,
            status,
            original_filename,
            stored_filename,
            video_blob_name,
            result_json,
            error_message,
            coach_feedback_note,
            created_at,
            updated_at,
            started_at,
            completed_at
        )
        SELECT
            id,
            NULL,
            analysis_type,
            status,
            original_filename,
            stored_filename,
            video_blob_name,
            result_json,
            error_message,
            NULL,
            created_at,
            updated_at,
            started_at,
            completed_at
        FROM jobs
        ON CONFLICT (id) DO NOTHING;
    END IF;
END
$$;
