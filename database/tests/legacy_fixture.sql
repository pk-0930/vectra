-- Synthetic data only. Includes unclaimed clients and ownerless analysis/jobs.
INSERT INTO users (id,email,password_hash,created_at,updated_at) VALUES
    (101,'owner-a@example.invalid','fixture-hash',now(),now()),
    (102,'owner-b@example.invalid','fixture-hash',now(),now());
INSERT INTO coaches (id,user_id,first_name,last_name,associated_gym,created_at,updated_at) VALUES
    (101,101,'Coach','A','Same gym label',now(),now()),
    (102,102,'Coach','B','Same gym label',now(),now());
INSERT INTO clients (id,coach_id,first_name,last_name,created_at,updated_at) VALUES
    (101,101,'Same','Name',now(),now()),
    (102,102,'Same','Name',now(),now());
INSERT INTO client_goals (client_id,goal_type,notes,created_at)
    VALUES (101,'strength','Preserve this history',now());
INSERT INTO client_progress_photos (client_id,blob_name,timeline_type,captured_on,created_at)
    VALUES (101,'fixture/progress.jpg','weekly','2026-10-17',now());
INSERT INTO nutrition_plans (client_id,period_type,period_start,period_end,title,content_json,pdf_blob_name,created_by_coach_id,created_at,updated_at)
    VALUES (101,'weekly','2026-10-17','2026-10-23','Nutrition','{"meals":[]}', 'fixture/nutrition.pdf',101,now(),now());
INSERT INTO workout_plans (client_id,period_type,period_start,period_end,title,content_json,pdf_blob_name,created_by_coach_id,created_at,updated_at)
    VALUES (101,'weekly','2026-10-17','2026-10-23','Workout','{"exercises":[]}','fixture/workout.pdf',101,now(),now());
INSERT INTO ai_plan_drafts (client_id,coach_id,plan_kind,status,period_type,period_start,period_end,title,content_json,source_context_json,generation_preferences_json,coach_prompt,model_name,created_at,updated_at)
    VALUES (101,101,'workout','draft','weekly','2026-10-17','2026-10-23','Private draft','{}','{}','{}','Fixture prompt','fixture-model',now(),now());
INSERT INTO form_analyses (id,client_id,analysis_type,status,original_filename,stored_filename,video_blob_name,result_json,created_at,updated_at) VALUES
    ('owned-analysis',101,'squat','completed','fixture.mp4','stored.mp4','fixture/video.mp4','{"score":70}',now(),now()),
    ('unowned-analysis',NULL,'squat','queued','unknown.mp4','unknown.mp4','fixture/unknown.mp4',NULL,now(),now());
INSERT INTO jobs (id,analysis_type,status,original_filename,stored_filename,video_blob_name,created_at,updated_at)
    VALUES ('legacy-job','squat','queued','old.mp4','old.mp4','fixture/old.mp4',now(),now());
SELECT setval(pg_get_serial_sequence('users','id'),102);
SELECT setval(pg_get_serial_sequence('coaches','id'),102);
SELECT setval(pg_get_serial_sequence('clients','id'),102);
