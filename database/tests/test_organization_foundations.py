"""Opt-in PostgreSQL/Flyway rehearsal; creates and removes its own Docker resources.

Run from the repository root:
    VECTRA_RUN_MIGRATION_TESTS=1 mobility-ai-service/venv/bin/python \
        -m unittest discover -s database/tests -v

Never reads application settings, .env, flyway.conf or a supplied database URL.
Requires Docker plus the repository's psycopg dependency. No existing database
or Docker volume is touched. Test passwords are generated for this run only.
"""
import concurrent.futures
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
import unittest
import uuid

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[2]
FLYWAY_IMAGE = "flyway/flyway:13.0.0"
ENABLED = os.environ.get("VECTRA_RUN_MIGRATION_TESTS") == "1"


@unittest.skipUnless(ENABLED, "Set VECTRA_RUN_MIGRATION_TESTS=1 for isolated Docker tests")
class DisposablePostgresTests(unittest.TestCase):
    @classmethod
    def docker(cls, *args, env=None):
        try:
            return subprocess.run(
                ["docker", *args], check=True, capture_output=True, text=True,
                env=env, timeout=180,
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            output = (exc.stdout + exc.stderr).replace(cls.password, "[redacted]")
            raise RuntimeError(f"Docker test command failed:\n{output}") from None

    @classmethod
    def setUpClass(cls):
        cls.resource = "vectra-schema-test-" + uuid.uuid4().hex[:12]
        cls.password = secrets.token_urlsafe(32)
        cls.docker("network", "create", cls.resource)
        cls.addClassCleanup(cls.docker, "network", "rm", cls.resource)
        env = dict(os.environ, POSTGRES_PASSWORD=cls.password)
        cls.docker(
            "run", "--detach", "--name", cls.resource,
            "--network", cls.resource, "--publish", "127.0.0.1::5432",
            "--tmpfs", "/var/lib/postgresql/data",
            "--env", "POSTGRES_PASSWORD", "postgres:16", env=env,
        )
        cls.addClassCleanup(cls.docker, "rm", "--force", cls.resource)
        cls.port = int(cls.docker("port", cls.resource, "5432/tcp").rsplit(":", 1)[1])
        deadline = time.monotonic() + 40
        while True:
            try:
                with cls.connect("postgres", autocommit=True):
                    break
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Disposable PostgreSQL did not become ready") from None
                time.sleep(0.25)

    @classmethod
    def connect(cls, database, **kwargs):
        return psycopg.connect(
            host="127.0.0.1", port=cls.port, user="postgres",
            password=cls.password, dbname=database, connect_timeout=3, **kwargs,
        )

    @classmethod
    def create_database(cls, name):
        with cls.connect("postgres", autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

    @classmethod
    def flyway(cls, database, command, *options):
        env = dict(
            os.environ,
            FLYWAY_URL=f"jdbc:postgresql://{cls.resource}:5432/{database}",
            FLYWAY_USER="postgres", FLYWAY_PASSWORD=cls.password,
        )
        defaults = [] if any(option.startswith("-baselineOnMigrate=") for option in options) else ["-baselineOnMigrate=false"]
        return cls.docker(
            "run", "--rm", "--network", cls.resource,
            "--volume", f"{ROOT / 'database/migrations'}:/flyway/sql:ro",
            "--env", "FLYWAY_URL", "--env", "FLYWAY_USER", "--env", "FLYWAY_PASSWORD",
            FLYWAY_IMAGE, "-locations=filesystem:/flyway/sql",
            "-schemas=public", "-defaultSchema=public", "-cleanDisabled=true",
            *defaults, *options, command, env=env,
        )

@unittest.skipUnless(ENABLED, "Set VECTRA_RUN_MIGRATION_TESTS=1 for isolated Docker tests")
class OrganizationFoundationTests(DisposablePostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_database("constraints")
        cls.flyway("constraints", "migrate", "-target=3")

    def setUp(self):
        self.connection = self.connect("constraints")
        self.addCleanup(self.connection.close)
        self.addCleanup(self.connection.rollback)
        self.user = self.insert("users", {
            "email": "person@example.invalid", "password_hash": "test-only-hash",
            "created_at": "2026-10-17", "updated_at": "2026-10-17",
        })
        self.coach = self.insert("coaches", {
            "user_id": self.user, "first_name": "Test", "last_name": "Coach",
            "created_at": "2026-10-17", "updated_at": "2026-10-17",
        })
        self.org = self.insert("organizations", {"name": "Gym A", "organization_type": "gym"})
        self.other = self.insert("organizations", {"name": "Coach B", "organization_type": "coaching"})
        self.relationship = self.insert("organization_relationships", {
            "organization_id": self.org, "user_id": self.user,
        })
        self.other_relationship = self.insert("organization_relationships", {
            "organization_id": self.other, "user_id": self.user,
        })
        self.client = self.client_record(
            organization_id=self.org, organization_relationship_id=self.relationship,
        )

    def insert(self, table, values):
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, values)),
            sql.SQL(", ").join(sql.Placeholder() for _ in values),
        )
        return self.connection.execute(query, list(values.values())).fetchone()[0]

    def client_record(self, **extra):
        return self.insert("clients", {
            "coach_id": self.coach, "first_name": "Test", "last_name": "Client",
            "created_at": "2026-10-17", "updated_at": "2026-10-17", **extra,
        })

    def rejected(self, exception, query, params=()):
        with self.assertRaises(exception):
            with self.connection.transaction():
                self.connection.execute(query, params)

    def test_fresh_install_validate_and_repeat_migrate(self):
        self.create_database("fresh")
        self.flyway("fresh", "migrate", "-target=3")
        # This regression intentionally stops at V3; later migrations are pending.
        self.flyway("fresh", "validate", "-ignoreMigrationPatterns=*:pending")
        self.flyway("fresh", "migrate", "-target=3")
        with self.connect("fresh") as connection:
            rows = connection.execute(
                "SELECT version, success FROM flyway_schema_history ORDER BY installed_rank"
            ).fetchall()
        self.assertEqual(rows, [("1", True), ("2", True), ("3", True)])

    def test_upgrade_preserves_all_legacy_rows_and_old_writes(self):
        self.create_database("upgrade")
        self.flyway("upgrade", "migrate", "-target=2")
        with self.connect("upgrade") as connection:
            connection.execute((ROOT / "database/tests/legacy_fixture.sql").read_text())
        self.assert_upgrade_preserved("upgrade")

    def test_populated_unversioned_baseline_adoption(self):
        self.create_database("adoption")
        with self.connect("adoption") as connection:
            connection.execute((ROOT / "database/migrations/V1__baseline.sql").read_text())
            connection.execute((ROOT / "database/tests/legacy_fixture.sql").read_text())
        self.flyway("adoption", "migrate", "-baselineOnMigrate=true", "-baselineVersion=1", "-target=2")
        self.assert_upgrade_preserved("adoption")
        with self.connect("adoption") as connection:
            self.assertEqual(connection.execute(
                "SELECT type FROM flyway_schema_history WHERE version='1'"
            ).fetchone()[0], "BASELINE")

    def assert_upgrade_preserved(self, database):
        tables = [
            "users", "coaches", "clients", "client_goals", "client_progress_photos",
            "nutrition_plans", "workout_plans", "ai_plan_drafts", "form_analyses", "jobs",
        ]
        with self.connect(database) as connection:
            before = {name: connection.execute(
                sql.SQL("SELECT row_to_json(t)::jsonb FROM {} t ORDER BY id").format(sql.Identifier(name))
            ).fetchall() for name in tables}
        self.flyway(database, "migrate", "-target=3")
        self.flyway(database, "validate", "-ignoreMigrationPatterns=*:pending")
        with self.connect(database) as connection:
            for name in tables:
                rows = connection.execute(sql.SQL(
                    "SELECT row_to_json(t)::jsonb FROM {} t ORDER BY id"
                ).format(sql.Identifier(name))).fetchall()
                if name == "clients":
                    for (row,) in rows:
                        self.assertIsNone(row.pop("organization_id"))
                        self.assertIsNone(row.pop("organization_relationship_id"))
                self.assertEqual(before[name], rows, name)
            self.assertEqual(connection.execute("SELECT count(*) FROM organizations").fetchone()[0], 0)
            # Exercise the actual existing adapter, not only an equivalent SQL insert.
            import sys
            sys.path.insert(0, str(ROOT / "mobility-ai-service"))
            from repositories.platform_repository import PostgresPlatformRepository
            from datetime import datetime, timezone

            class TestConfig:
                def connection_kwargs(config_self):
                    return dict(host="127.0.0.1", port=self.port, user="postgres",
                                password=self.password, dbname=database)

            repository = PostgresPlatformRepository(TestConfig())
            now = datetime.now(timezone.utc)
            client = repository.create_client(dict(
                coach_id=101, first_name="After", last_name="Migration", dob=None,
                gender=None, height_cm=None, weight_kg=None, is_active=True,
                created_at=now, updated_at=now,
            ))
            self.assertIsNone(client["organization_id"])
            self.assertEqual(repository.fetch_client(client["id"], 101)["first_name"], "After")
            self.assertIsNone(repository.fetch_client(client["id"], 102))

    def test_relationship_unique_per_business_but_user_can_join_many(self):
        self.assertNotEqual(self.relationship, self.other_relationship)
        self.rejected(psycopg.errors.UniqueViolation,
                      "INSERT INTO organization_relationships (organization_id,user_id) VALUES (%s,%s)",
                      (self.org, self.user))

    def test_cross_business_roles_claims_and_assignments_fail(self):
        for query, params in [
            ("INSERT INTO organization_staff_roles (organization_id,relationship_id,role) VALUES (%s,%s,'trainer')",
             (self.other, self.relationship)),
            ("UPDATE clients SET organization_relationship_id=%s WHERE id=%s",
             (self.other_relationship, self.client)),
            ("INSERT INTO trainer_client_assignments (organization_id,trainer_relationship_id,client_id) VALUES (%s,%s,%s)",
             (self.other, self.other_relationship, self.client)),
            ("INSERT INTO trainer_client_assignments (organization_id,trainer_relationship_id,client_id) VALUES (%s,%s,%s)",
             (self.org, self.other_relationship, self.client)),
        ]:
            with self.subTest(query=query):
                self.rejected(psycopg.errors.ForeignKeyViolation, query, params)

    def test_unclaimed_clients_allowed_but_claim_cannot_bypass_scope(self):
        self.client_record()
        self.client_record(organization_id=self.org)
        self.client_record(organization_id=self.org)
        self.rejected(psycopg.errors.CheckViolation,
                      "UPDATE clients SET organization_id=NULL WHERE id=%s", (self.client,))
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.connection.transaction():
                self.client_record(organization_id=self.org,
                                   organization_relationship_id=self.relationship)

    def test_role_revocation_preserves_member_and_other_business(self):
        role = self.insert("organization_staff_roles", {
            "organization_id": self.org, "relationship_id": self.relationship, "role": "trainer",
        })
        self.insert("organization_staff_roles", {
            "organization_id": self.other, "relationship_id": self.other_relationship, "role": "owner",
        })
        self.connection.execute("UPDATE organization_staff_roles SET revoked_at=CURRENT_TIMESTAMP WHERE id=%s", (role,))
        self.assertEqual(self.connection.execute(
            "SELECT organization_relationship_id FROM clients WHERE id=%s", (self.client,)
        ).fetchone()[0], self.relationship)
        self.assertEqual(self.connection.execute(
            "SELECT status FROM organization_relationships WHERE id=%s", (self.relationship,)
        ).fetchone()[0], "active")
        self.assertEqual(self.connection.execute(
            "SELECT count(*) FROM organization_staff_roles WHERE organization_id=%s AND revoked_at IS NULL",
            (self.other,),
        ).fetchone()[0], 1)
        self.insert("organization_staff_roles", {
            "organization_id": self.org, "relationship_id": self.relationship, "role": "trainer",
        })

    def test_assignment_duplicate_blocked_and_history_retained(self):
        values = dict(organization_id=self.org, trainer_relationship_id=self.relationship, client_id=self.client)
        assignment = self.insert("trainer_client_assignments", values)
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.connection.transaction():
                self.insert("trainer_client_assignments", values)
        self.connection.execute("UPDATE trainer_client_assignments SET ended_at=CURRENT_TIMESTAMP WHERE id=%s", (assignment,))
        self.insert("trainer_client_assignments", values)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM trainer_client_assignments").fetchone()[0], 2)

    def test_invalid_types_roles_and_time_ranges_fail(self):
        for query in [
            "INSERT INTO organizations(name,organization_type) VALUES ('Gym','unknown')",
            "INSERT INTO organizations(name,organization_type) VALUES ('  ','gym')",
            "INSERT INTO organizations(name,organization_type,billing_transition) VALUES ('Gym','gym','paid')",
            f"INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES ({self.org},{self.relationship},'member')",
            f"INSERT INTO organization_staff_roles(organization_id,relationship_id,role,granted_at,revoked_at) VALUES ({self.org},{self.relationship},'trainer','2026-10-17','2026-10-16')",
            f"INSERT INTO trainer_client_assignments(organization_id,trainer_relationship_id,client_id,started_at,ended_at) VALUES ({self.org},{self.relationship},{self.client},'2026-10-17','2026-10-16')",
        ]:
            with self.subTest(query=query):
                self.rejected(psycopg.errors.CheckViolation, query)

    def test_legacy_mapping_is_one_to_one_and_preserves_identity(self):
        self.connection.execute("INSERT INTO legacy_coach_organizations(coach_id,organization_id) VALUES (%s,%s)", (self.coach, self.other))
        self.rejected(psycopg.errors.UniqueViolation,
                      "INSERT INTO legacy_coach_organizations(coach_id,organization_id) VALUES (%s,%s)",
                      (self.coach, self.org))
        self.rejected(psycopg.errors.ForeignKeyViolation, "DELETE FROM coaches WHERE id=%s", (self.coach,))
        self.rejected(psycopg.errors.ForeignKeyViolation, "DELETE FROM organizations WHERE id=%s", (self.other,))

    def test_concurrent_role_grants_only_create_one_current_role(self):
        # Separate committed fixture/database keeps the other tests rollback-only.
        self.create_database("concurrency")
        self.flyway("concurrency", "migrate", "-target=3")
        with self.connect("concurrency") as connection:
            user = connection.execute("INSERT INTO users(email,password_hash,created_at,updated_at) VALUES ('test@example.invalid','test',now(),now()) RETURNING id").fetchone()[0]
            org = connection.execute("INSERT INTO organizations(name,organization_type) VALUES ('Test','gym') RETURNING id").fetchone()[0]
            relationship = connection.execute("INSERT INTO organization_relationships(organization_id,user_id) VALUES (%s,%s) RETURNING id", (org, user)).fetchone()[0]
        barrier = threading.Barrier(2)

        def grant():
            try:
                with self.connect("concurrency") as connection:
                    connection.execute("SET lock_timeout = '5s'")
                    barrier.wait(timeout=10)
                    connection.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES (%s,%s,'trainer')", (org, relationship))
                return "created"
            except psycopg.errors.UniqueViolation:
                return "duplicate"

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: grant(), range(2)))
        self.assertCountEqual(results, ["created", "duplicate"])


if __name__ == "__main__":
    unittest.main()
