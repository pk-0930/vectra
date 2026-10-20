"""V4 backfill acceptance tests using synthetic data in disposable PostgreSQL."""
from datetime import datetime, timezone
import subprocess
import unittest
import uuid

from psycopg import sql
import test_organization_foundations as foundations


@unittest.skipUnless(foundations.ENABLED, "Set VECTRA_RUN_MIGRATION_TESTS=1")
class LegacyBackfillTests(foundations.DisposablePostgresTests):
    def setUp(self):
        self.database = "backfill_" + uuid.uuid4().hex[:10]
        self.create_database(self.database)
        self.flyway(self.database, "migrate", "-target=3")
        with self.connect(self.database) as connection:
            connection.execute(
                (foundations.ROOT / "database/tests/legacy_fixture.sql").read_text()
            )

    def migrate(self):
        self.flyway(self.database, "migrate", "-target=4")
        self.flyway(self.database, "validate", "-ignoreMigrationPatterns=*:pending")

    def snapshot(self, connection):
        tables = (
            "users", "coaches", "clients", "client_goals", "client_progress_photos",
            "nutrition_plans", "workout_plans", "ai_plan_drafts", "form_analyses", "jobs",
        )
        return {
            name: connection.execute(sql.SQL(
                "SELECT row_to_json(t)::jsonb - 'organization_id' "
                "FROM {} t ORDER BY id"
            ).format(sql.Identifier(name))).fetchall()
            for name in tables
        }

    def issues(self, connection):
        return set(connection.execute(
            "SELECT issue_code, entity_type, entity_id FROM legacy_ownership_issues"
        ).fetchall())

    def test_backfill_preserves_history_and_separates_same_name_businesses(self):
        with self.connect(self.database) as connection:
            before = self.snapshot(connection)
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertEqual(before, self.snapshot(connection))
            mappings = connection.execute(
                "SELECT coach_id, organization_id FROM legacy_coach_organizations "
                "ORDER BY coach_id"
            ).fetchall()
            self.assertEqual([row[0] for row in mappings], [101, 102])
            self.assertEqual(len({row[1] for row in mappings}), 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM organizations WHERE organization_type='coaching' "
                "AND billing_transition='legacy_access' AND status='active'"
            ).fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM clients c JOIN legacy_coach_organizations m "
                "ON m.coach_id=c.coach_id AND m.organization_id=c.organization_id "
                "WHERE c.organization_relationship_id IS NULL"
            ).fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM coaches c JOIN legacy_coach_organizations m "
                "ON m.coach_id=c.id JOIN organization_relationships r "
                "ON r.organization_id=m.organization_id AND r.user_id=c.user_id "
                "JOIN organization_staff_roles s ON s.organization_id=r.organization_id "
                "AND s.relationship_id=r.id WHERE s.role='owner' AND s.revoked_at IS NULL"
            ).fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM trainer_client_assignments WHERE ended_at IS NULL"
            ).fetchone()[0], 2)
            self.assertEqual(self.issues(connection), {
                ("analysis_owner_unresolved", "form_analysis", "unowned-analysis"),
                ("legacy_job_requires_review", "job", "legacy-job"),
            })

    def test_fresh_install_and_repeat_migrate_do_not_duplicate_records(self):
        fresh = "empty_" + uuid.uuid4().hex[:10]
        self.create_database(fresh)
        self.flyway(fresh, "migrate", "-target=4")
        self.flyway(fresh, "validate", "-ignoreMigrationPatterns=*:pending")
        with self.connect(fresh) as connection:
            self.assertEqual(connection.execute(
                "SELECT version FROM flyway_schema_history ORDER BY installed_rank"
            ).fetchall(), [("1",), ("2",), ("3",), ("4",)])
            self.assertEqual(self.issues(connection), set())
        self.migrate()
        with self.connect(self.database) as connection:
            before = connection.execute(
                "SELECT * FROM legacy_coach_organizations ORDER BY coach_id"
            ).fetchall()
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertEqual(connection.execute(
                "SELECT * FROM legacy_coach_organizations ORDER BY coach_id"
            ).fetchall(), before)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM organization_staff_roles"
            ).fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM trainer_client_assignments"
            ).fetchone()[0], 2)

    def test_inactive_clients_are_scoped_without_current_assignments(self):
        with self.connect(self.database) as connection:
            connection.execute("UPDATE clients SET is_active=false WHERE id=102")
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertIsNotNone(connection.execute(
                "SELECT organization_id FROM clients WHERE id=102"
            ).fetchone()[0])
            self.assertEqual(connection.execute(
                "SELECT client_id FROM trainer_client_assignments"
            ).fetchall(), [(101,)])

    def test_author_conflicts_are_reported_without_rewriting_records(self):
        with self.connect(self.database) as connection:
            connection.execute("UPDATE nutrition_plans SET created_by_coach_id=102")
            connection.execute("UPDATE workout_plans SET created_by_coach_id=102")
            connection.execute("UPDATE ai_plan_drafts SET coach_id=102")
            before = self.snapshot(connection)
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertEqual(before, self.snapshot(connection))
            codes = {row[0] for row in self.issues(connection)}
            self.assertTrue({"nutrition_author_conflict", "workout_author_conflict",
                             "draft_author_conflict"}.issubset(codes))

    def test_new_legacy_writes_after_migration_are_visible_in_report(self):
        self.migrate()
        with self.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO users(id,email,password_hash,created_at,updated_at) "
                "VALUES(103,'late@example.invalid','fixture',now(),now())"
            )
            connection.execute(
                "INSERT INTO coaches(id,user_id,first_name,last_name,created_at,updated_at) "
                "VALUES(103,103,'Late','Coach',now(),now())"
            )
            connection.execute(
                "INSERT INTO clients(id,coach_id,first_name,last_name,created_at,updated_at) "
                "VALUES(103,101,'Late','Client',now(),now())"
            )
            self.assertIn(("coach_mapping_missing", "coach", "103"), self.issues(connection))
            self.assertIn(("client_scope_missing", "client", "103"), self.issues(connection))
        # Flyway repeat is not an implicit catch-up or a grant-restoration operation.
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertIn(("coach_mapping_missing", "coach", "103"), self.issues(connection))
            self.assertIsNone(connection.execute(
                "SELECT organization_id FROM clients WHERE id=103"
            ).fetchone()[0])

    def test_conflicting_scope_aborts_atomically_and_can_retry_after_correction(self):
        with self.connect(self.database) as connection:
            org = connection.execute(
                "INSERT INTO organizations(name,organization_type) VALUES('Existing','gym') "
                "RETURNING id"
            ).fetchone()[0]
            connection.execute("UPDATE clients SET organization_id=%s WHERE id=101", (org,))
        with self.assertRaisesRegex(RuntimeError, "Existing client business conflicts"):
            self.migrate()
        with self.connect(self.database) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM legacy_coach_organizations"
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM organizations").fetchone()[0], 1)
            self.assertIsNone(connection.execute(
                "SELECT to_regclass('public.legacy_ownership_issues')"
            ).fetchone()[0])
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM flyway_schema_history WHERE version='4'"
            ).fetchone()[0], 0)
            # Test-only correction; real conflicts require evidence and review.
            connection.execute("UPDATE clients SET organization_id=NULL WHERE id=101")
        self.migrate()

    def seed_existing_mapping(self, connection):
        org = connection.execute(
            "INSERT INTO organizations(name,organization_type,billing_transition) "
            "VALUES('Existing coaching business','coaching','legacy_access') RETURNING id"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO legacy_coach_organizations(coach_id,organization_id) VALUES(101,%s)", (org,)
        )
        relationship = connection.execute(
            "INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,101) "
            "RETURNING id", (org,)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO organization_staff_roles(organization_id,relationship_id,role) "
            "VALUES(%s,%s,'owner')", (org, relationship),
        )
        return org, relationship

    def test_revoked_owner_is_never_reactivated_by_backfill(self):
        with self.connect(self.database) as connection:
            # Use equal timestamps so the fixture obeys the role date constraint.
            org, relationship = self.seed_existing_mapping(connection)
            connection.execute(
                "UPDATE organization_staff_roles SET revoked_at=granted_at "
                "WHERE relationship_id=%s", (relationship,)
            )
        with self.assertRaisesRegex(RuntimeError, "Legacy mapping conflicts"):
            self.migrate()
        with self.connect(self.database) as connection:
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM organization_staff_roles WHERE revoked_at IS NULL"
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM organizations").fetchone()[0], 1)

    def test_existing_mapping_and_ended_assignment_are_preserved(self):
        with self.connect(self.database) as connection:
            org, relationship = self.seed_existing_mapping(connection)
            connection.execute("UPDATE clients SET organization_id=%s WHERE id=101", (org,))
            connection.execute(
                "INSERT INTO trainer_client_assignments "
                "(organization_id,trainer_relationship_id,client_id,started_at,ended_at) "
                "VALUES(%s,%s,101,now(),now())", (org, relationship)
            )
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertEqual(connection.execute(
                "SELECT organization_id FROM legacy_coach_organizations WHERE coach_id=101"
            ).fetchone()[0], org)
            self.assertEqual(connection.execute(
                "SELECT count(*) FROM trainer_client_assignments WHERE client_id=101 "
                "AND ended_at IS NULL"
            ).fetchone()[0], 0)
            self.assertIn(("client_assignment_missing", "client", "101"), self.issues(connection))

    def test_busy_source_times_out_without_partial_mapping(self):
        with self.connect(self.database) as blocker:
            blocker.execute("UPDATE clients SET first_name=first_name WHERE id=101")
            with self.assertRaisesRegex(RuntimeError, "lock timeout"):
                self.migrate()
            blocker.rollback()
        with self.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM organizations").fetchone()[0], 0)
        self.migrate()

    def test_adopted_database_without_optional_jobs_table(self):
        with self.connect(self.database) as connection:
            connection.execute("DROP TABLE jobs")
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertFalse(any(row[1] == "job" for row in self.issues(connection)))
            self.assertIn(("analysis_owner_unresolved", "form_analysis", "unowned-analysis"),
                          self.issues(connection))

    def test_unversioned_adoption_through_v4_and_read_only_report(self):
        adopted = "adopt_" + uuid.uuid4().hex[:10]
        self.create_database(adopted)
        with self.connect(adopted) as connection:
            connection.execute(
                (foundations.ROOT / "database/migrations/V1__baseline.sql").read_text()
            )
            connection.execute(
                (foundations.ROOT / "database/tests/legacy_fixture.sql").read_text()
            )
        self.flyway(adopted, "migrate", "-target=4",
                    "-baselineOnMigrate=true", "-baselineVersion=1")
        self.flyway(adopted, "validate", "-ignoreMigrationPatterns=*:pending")
        with self.connect(adopted, autocommit=True) as connection:
            cursor = connection.execute(
                (foundations.ROOT / "database/verification/legacy_backfill.sql").read_text()
            )
            results = []
            while True:
                if cursor.description:
                    results.append(cursor.fetchall())
                if not cursor.nextset():
                    break
            # V2 copied the ownerless legacy job into analyses; both remain unresolved.
            self.assertEqual(results[0], [(2, 2, 2, 2, 0, 2, 3)])
            self.assertIn(("analysis_owner_unresolved", "form_analysis", "legacy-job"),
                          self.issues(connection))
            self.assertEqual(connection.execute(
                "SELECT type FROM flyway_schema_history WHERE version='1'"
            ).fetchone()[0], "BASELINE")

    def test_restore_copy_rehearsal_and_existing_repository_access(self):
        # Actual pg_dump/restore of a synthetic V3 database before applying V4.
        backup = self.docker(
            "exec", self.resource, "pg_dump", "--username=postgres",
            "--no-owner", "--no-privileges", "--dbname=" + self.database,
        )
        restored = "restore_" + uuid.uuid4().hex[:10]
        self.create_database(restored)
        subprocess.run(
            ["docker", "exec", "-i", self.resource, "psql", "--username=postgres",
             "--dbname=" + restored, "--set=ON_ERROR_STOP=1"],
            input=backup, text=True, capture_output=True, check=True, timeout=30,
        )
        self.database = restored
        self.migrate()
        with self.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM clients").fetchone()[0], 2)
        import sys
        sys.path.insert(0, str(foundations.ROOT / "mobility-ai-service"))
        from config.postgres_config import PostgresConfig
        from repositories.platform_repository import PostgresPlatformRepository
        repository = PostgresPlatformRepository(PostgresConfig(
            host="127.0.0.1", port=self.port, dbname=restored, user="postgres",
            password=self.password, sslmode="disable",
        ))
        self.assertEqual(repository.fetch_client(101, 101)["id"], 101)
        self.assertIsNone(repository.fetch_client(101, 102))
        self.assertEqual([row["id"] for row in repository.list_clients(102)], [102])
        now = datetime.now(timezone.utc)
        created = repository.create_client(dict(
            coach_id=101, first_name="After", last_name="V4", dob=None,
            gender=None, height_cm=None, weight_kg=None, is_active=True,
            created_at=now, updated_at=now,
        ))
        self.assertIsNone(created["organization_id"])
        with self.connect(self.database) as connection:
            self.assertIn(("client_scope_missing", "client", str(created["id"])), self.issues(connection))


if __name__ == "__main__":
    unittest.main()
