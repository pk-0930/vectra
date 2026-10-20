"""Real SQL coverage of current identity context; no deployment or external DB."""
import sys
import unittest

import test_organization_foundations as foundations

sys.path.insert(0, str(foundations.ROOT / 'mobility-ai-service'))
from config.postgres_config import PostgresConfig
from repositories.platform_repository import PostgresPlatformRepository


@unittest.skipUnless(foundations.ENABLED, 'Set VECTRA_RUN_MIGRATION_TESTS=1')
class IdentityContextTests(foundations.DisposablePostgresTests):
    def test_context_refresh_preserves_member_and_other_business_after_role_revocation(self):
        self.create_database('identity')
        self.flyway('identity', 'migrate', '-target=4')
        with self.connect('identity') as c:
            c.execute((foundations.ROOT / 'database/tests/legacy_fixture.sql').read_text())
        self.flyway('identity', 'migrate')
        repo = PostgresPlatformRepository(PostgresConfig(
            host='127.0.0.1', port=self.port, dbname='identity', user='postgres',
            password=self.password, sslmode='disable',
        ))
        with self.connect('identity') as c:
            # User 102 retains their own business plus member+trainer in coach 101's business.
            org = c.execute('SELECT organization_id FROM clients WHERE id=101').fetchone()[0]
            rel = c.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,102) RETURNING id', (org,)).fetchone()[0]
            c.execute('UPDATE clients SET organization_relationship_id=%s WHERE id=101', (rel,))
            c.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'trainer')", (org, rel))
        contexts = repo.list_user_organizations(102)
        self.assertEqual(len(contexts), 2)
        member = next(r for r in contexts if r['organization_id'] == org)
        self.assertEqual(member['staff_roles'], ['trainer'])
        self.assertEqual(member['client_id'], 101)
        with self.connect('identity') as c:
            c.execute('UPDATE organization_staff_roles SET revoked_at=now() WHERE relationship_id=%s', (rel,))
        member = next(r for r in repo.list_user_organizations(102) if r['organization_id'] == org)
        self.assertEqual(member['staff_roles'], [])
        self.assertEqual(member['client_id'], 101)
        self.assertEqual(len(repo.list_user_organizations(102)), 2)
        with self.connect('identity') as c:
            c.execute("UPDATE organization_relationships SET status='inactive' WHERE id=%s", (rel,))
        self.assertEqual(len(repo.list_user_organizations(102)), 1)
        with self.connect('identity') as c:
            c.execute("UPDATE organizations SET status='inactive'")
        self.assertEqual(repo.list_user_organizations(102), [])
        self.assertEqual(repo.list_user_organizations(999999), [])
