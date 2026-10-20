"""V5 catch-up and real PostgreSQL repository isolation tests."""
from datetime import datetime, timezone
import json
import subprocess
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
from psycopg import sql
import test_organization_foundations as foundations

sys.path.insert(0, str(foundations.ROOT / "mobility-ai-service"))
from config.postgres_config import PostgresConfig
from repositories.platform_repository import PostgresPlatformRepository
from repositories.organization_repository import OrganizationRepository


@unittest.skipUnless(foundations.ENABLED, "Set VECTRA_RUN_MIGRATION_TESTS=1")
class OrganizationScopingTests(foundations.DisposablePostgresTests):
    def setUp(self):
        self.database = "scope_" + uuid.uuid4().hex[:10]
        self.create_database(self.database)
        self.flyway(self.database, "migrate", "-target=4")
        with self.connect(self.database) as connection:
            # All fixture rows arrive AFTER V4, simulating the old writer window.
            connection.execute((foundations.ROOT / "database/tests/legacy_fixture.sql").read_text())
            connection.execute("UPDATE workout_plans SET created_by_coach_id=102")
            connection.execute("UPDATE ai_plan_drafts SET coach_id=102")
            self.before = self.snapshot(connection)
        self.flyway(self.database, "migrate", "-target=5")
        self.config = PostgresConfig(
            host="127.0.0.1", port=self.port, dbname=self.database,
            user="postgres", password=self.password, sslmode="disable",
        )
        self.legacy = PostgresPlatformRepository(self.config)
        with self.connect(self.database) as connection:
            self.org_a = connection.execute(
                "SELECT organization_id FROM legacy_coach_organizations WHERE coach_id=101"
            ).fetchone()[0]
            self.org_b = connection.execute(
                "SELECT organization_id FROM legacy_coach_organizations WHERE coach_id=102"
            ).fetchone()[0]
        self.a = self.legacy.for_organization(self.org_a)
        self.b = self.legacy.for_organization(self.org_b)
        self.now = datetime.now(timezone.utc)

    def snapshot(self, connection):
        return {
            table: connection.execute(sql.SQL(
                "SELECT row_to_json(t)::jsonb - 'organization_id' FROM {} t ORDER BY id"
            ).format(sql.Identifier(table))).fetchall()
            for table in (
                "users", "coaches", "clients", "client_goals", "client_progress_photos",
                "nutrition_plans", "workout_plans", "ai_plan_drafts", "form_analyses", "jobs",
            )
        }

    def client_payload(self):
        return dict(first_name="New", last_name="Client", dob=None, gender=None,
                    height_cm=None, weight_kg=None, is_active=True,
                    created_at=self.now, updated_at=self.now)

    def test_catchup_preserves_records_and_repeat_flyway_is_stable(self):
        self.flyway(self.database, "validate", "-ignoreMigrationPatterns=*:pending")
        self.flyway(self.database, "migrate", "-target=5")
        with self.connect(self.database) as connection:
            self.assertEqual(self.before, self.snapshot(connection))
            self.assertEqual(connection.execute("SELECT count(*) FROM organizations").fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM clients WHERE organization_id IS NULL"
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM organizations WHERE billing_transition='legacy_access'"
            ).fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT version FROM flyway_schema_history ORDER BY installed_rank"
            ).fetchall(), [("1",), ("2",), ("3",), ("4",), ("5",)])

    def test_business_scoped_client_reads_and_writes_reject_other_ids(self):
        self.assertEqual([c["id"] for c in self.a.list_clients()], [101])
        self.assertIsNone(self.a.fetch_client(102))
        self.assertIsNone(self.a.update_client(102, {"first_name": "Wrong"}))
        self.assertEqual(self.b.fetch_client(102)["first_name"], "Same")
        with self.assertRaises(psycopg.errors.RaiseException):
            self.a.create_client(coach_id=102, payload=self.client_payload())
        with self.assertRaises(ValueError):
            self.a.create_client(coach_id=101, payload={**self.client_payload(), "organization_id": self.org_b})
        created = self.a.create_client(coach_id=101, payload=self.client_payload())
        self.assertEqual(created["organization_id"], self.org_a)
        self.assertIsNone(self.b.fetch_client(created["id"]))

    def test_all_scoped_descendant_reads_and_mutations(self):
        cases = {
            "client_goals": dict(goal_type="strength", is_current=True, created_at=self.now),
            "client_progress_photos": dict(blob_name="new/photo.jpg", timeline_type="weekly",
                                          captured_on="2026-10-17", created_at=self.now),
            "nutrition_plans": dict(period_type="weekly", period_start="2026-10-17", period_end="2026-10-23",
                                    title="Scoped", content_json={"meals": []}, created_by_coach_id=101,
                                    created_at=self.now, updated_at=self.now),
            "workout_plans": dict(period_type="weekly", period_start="2026-10-17", period_end="2026-10-23",
                                  title="Scoped", content_json={"exercises": []}, created_by_coach_id=101,
                                  created_at=self.now, updated_at=self.now),
            "ai_plan_drafts": dict(coach_id=101, plan_kind="workout", status="draft", period_type="weekly",
                                   period_start="2026-10-17", period_end="2026-10-23", title="Scoped draft",
                                   content_json={}, source_context_json={}, generation_preferences_json={},
                                   coach_prompt="Test", model_name="fixture", created_at=self.now, updated_at=self.now),
            "form_analyses": dict(id="new-analysis", analysis_type="squat", status="queued",
                                  original_filename="new.mp4", stored_filename="new.mp4", video_blob_name="new/video.mp4",
                                  created_at=self.now, updated_at=self.now),
        }
        for kind, payload in cases.items():
            with self.subTest(kind=kind):
                row = self.a.create_record(kind, client_id=101, payload=payload)
                self.assertEqual(self.a.fetch_record(kind, row["id"])["organization_id"], self.org_a)
                self.assertIsNone(self.b.fetch_record(kind, row["id"]))
                self.assertEqual(self.b.list_records(kind, client_id=101), [])
                field = "caption" if kind == "client_progress_photos" else "notes" if kind == "client_goals" else "updated_at"
                value = "Wrong" if field in {"caption", "notes"} else self.now
                self.assertIsNone(self.b.update_record(kind, row["id"], {field: value}))
                with self.assertRaises(ValueError):
                    self.b.create_record(kind, client_id=101, payload=payload)
        self.assertIsNone(self.b.resolve_photo("new/photo.jpg"))
        self.assertEqual(self.a.resolve_photo("new/photo.jpg")["client_id"], 101)

    def test_quarantined_records_are_hidden_from_legacy_and_scoped_reads(self):
        self.assertIsNone(self.legacy.fetch_form_analysis("unowned-analysis"))
        self.assertIsNone(self.legacy.fetch_form_analysis_for_coach("unowned-analysis", 101))
        self.assertIsNone(self.legacy.fetch_plan("workout_plans", 1, 101))
        self.assertIsNone(self.legacy.fetch_plan_draft(1, 102))
        self.assertIsNone(self.legacy.mark_form_analysis_running("unowned-analysis", self.now))
        self.assertIsNone(self.legacy.update_form_analysis_feedback("unowned-analysis", "Wrong", self.now))
        for repo in (self.a, self.b):
            self.assertIsNone(repo.fetch_record("form_analyses", "unowned-analysis"))
            self.assertIsNone(repo.fetch_record("workout_plans", 1))
            self.assertIsNone(repo.fetch_record("ai_plan_drafts", 1))
        self.assertEqual([r["id"] for r in self.legacy.fetch_form_analyses(101, 20, 101)], ["owned-analysis"])
        self.assertEqual(self.legacy.fetch_form_analyses(101, 20, 102), [])
        with self.connect(self.database) as connection:
            self.assertEqual(set(connection.execute(
                "SELECT record_type,record_id FROM quarantined_coaching_records"
            ).fetchall()), {("workout_plans", "1"), ("ai_plan_drafts", "1"), ("form_analyses", "unowned-analysis")})

    def test_old_writer_creates_scoped_coaches_clients_and_descendants(self):
        user = self.legacy.create_user(dict(email="new@example.invalid", password_hash="fixture",
                                            created_at=self.now, updated_at=self.now))
        coach = self.legacy.create_coach(dict(user_id=user["id"], first_name="New", last_name="Coach",
            dob=None, gender=None, mobile=None, years_of_experience=0, associated_gym=None,
            clients_trained=0, created_at=self.now, updated_at=self.now))
        client = self.legacy.create_client({**self.client_payload(), "coach_id": coach["id"]})
        with self.connect(self.database) as connection:
            self.assertEqual(connection.execute(
                "SELECT billing_transition FROM organizations WHERE id=%s", (client["organization_id"],)
            ).fetchone()[0], "none")
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM trainer_client_assignments WHERE client_id=%s", (client["id"],)
            ).fetchone()[0], 1)
        plan = self.legacy.create_plan("nutrition_plans", dict(
            client_id=client["id"], period_type="weekly", period_start="2026-10-17", period_end="2026-10-23",
            title="Legacy", content_json=json.dumps({"meals": []}), pdf_blob_name=None,
            created_by_coach_id=coach["id"], created_at=self.now, updated_at=self.now))
        self.assertEqual(plan["organization_id"], client["organization_id"])
        self.assertEqual(self.legacy.fetch_plan("nutrition_plans", plan["id"], coach["id"])["id"], plan["id"])
        self.assertIsNone(self.a.fetch_record("nutrition_plans", plan["id"]))

    def test_direct_sql_cannot_move_or_forge_ownership(self):
        queries = [
            ("UPDATE clients SET organization_id=%s WHERE id=101", (self.org_b,)),
            ("UPDATE form_analyses SET client_id=102 WHERE id='owned-analysis'", ()),
            ("UPDATE nutrition_plans SET organization_id=%s WHERE id=1", (self.org_b,)),
            ("UPDATE nutrition_plans SET created_by_coach_id=102 WHERE id=1", ()),
            ("INSERT INTO form_analyses(id,client_id,organization_id,analysis_type,status,original_filename,stored_filename,video_blob_name,created_at,updated_at) "
             "VALUES('forged',101,%s,'squat','queued','a','a','a',now(),now())", (self.org_b,)),
        ]
        for query, params in queries:
            with self.subTest(query=query), self.assertRaises(psycopg.errors.RaiseException):
                with self.connect(self.database) as connection:
                    connection.execute(query, params)

    def test_claim_is_scoped_and_concurrent_claims_only_start_once(self):
        self.a.update_record("form_analyses", "owned-analysis", {"status": "queued"})
        self.assertIsNone(self.b.claim_analysis("owned-analysis", self.now))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.a.claim_analysis("owned-analysis", self.now), range(2)))
        self.assertEqual(sum(row is not None for row in results), 1)

    def test_new_unowned_analysis_and_unsupported_table_are_rejected(self):
        with self.assertRaises(psycopg.errors.RaiseException):
            with self.connect(self.database) as connection:
                connection.execute(
                    "INSERT INTO form_analyses(id,analysis_type,status,original_filename,stored_filename,video_blob_name,created_at,updated_at) "
                    "VALUES('orphan','squat','queued','a','a','a',now(),now())"
                )
        for table in ("users", "jobs", "nutrition_plans; DROP TABLE users"):
            with self.assertRaises(ValueError):
                self.a.fetch_record(table, 1)
            with self.assertRaises(ValueError):
                self.legacy.fetch_plan(table, 1, 101)

    def test_approved_plan_must_belong_to_same_client_and_business(self):
        draft = self.a.create_record("ai_plan_drafts", client_id=101, payload=dict(
            coach_id=101, plan_kind="nutrition", status="draft", period_type="weekly",
            period_start="2026-10-17", period_end="2026-10-23", title="Draft",
            content_json={}, source_context_json={}, generation_preferences_json={},
            coach_prompt="Fixture", model_name="fixture", created_at=self.now, updated_at=self.now,
        ))
        other = self.b.create_record("nutrition_plans", client_id=102, payload=dict(
            period_type="weekly", period_start="2026-10-17", period_end="2026-10-23",
            title="Other", content_json={}, created_by_coach_id=102,
            created_at=self.now, updated_at=self.now,
        ))
        with self.assertRaises(psycopg.errors.RaiseException):
            self.a.update_record("ai_plan_drafts", draft["id"], {"approved_plan_id": other["id"]})
        self.assertEqual(self.a.update_record("ai_plan_drafts", draft["id"], {
            "approved_plan_id": 1, "status": "approved",
        })["approved_plan_id"], 1)

    def test_fresh_install_and_restored_v4_copy_support_current_adapter(self):
        fresh = "fresh_" + uuid.uuid4().hex[:10]
        self.create_database(fresh)
        self.flyway(fresh, "migrate")
        self.flyway(fresh, "validate")
        source = "source_" + uuid.uuid4().hex[:10]
        self.create_database(source)
        self.flyway(source, "migrate", "-target=4")
        with self.connect(source) as connection:
            connection.execute((foundations.ROOT / "database/tests/legacy_fixture.sql").read_text())
        backup = self.docker("exec", self.resource, "pg_dump", "--username=postgres",
                             "--no-owner", "--no-privileges", "--dbname=" + source)
        restored = "restore_" + uuid.uuid4().hex[:10]
        self.create_database(restored)
        subprocess.run(
            ["docker", "exec", "-i", self.resource, "psql", "--username=postgres",
             "--dbname=" + restored, "--set=ON_ERROR_STOP=1"],
            input=backup, text=True, capture_output=True, check=True, timeout=30,
        )
        self.flyway(restored, "migrate")
        self.flyway(restored, "validate")
        with self.connect(restored) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM clients").fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM clients WHERE organization_id IS NOT NULL"
            ).fetchone()[0], 2)

    def test_catchup_does_not_regrant_revoked_owner(self):
        database = "revoked_" + uuid.uuid4().hex[:10]
        self.create_database(database)
        self.flyway(database, "migrate", "-target=3")
        with self.connect(database) as connection:
            connection.execute((foundations.ROOT / "database/tests/legacy_fixture.sql").read_text())
        self.flyway(database, "migrate", "-target=4")
        with self.connect(database) as connection:
            connection.execute("UPDATE organization_staff_roles SET revoked_at=granted_at")
        self.flyway(database, "migrate")
        with self.connect(database) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM organization_staff_roles WHERE revoked_at IS NULL"
            ).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
