import unittest
from unittest.mock import Mock

from repositories.job_repository import PostgresJobRepository
from repositories.organization_repository import OrganizationRepository
from repositories.platform_repository import PostgresPlatformRepository


class OrganizationRepositoryTests(unittest.TestCase):
    def test_invalid_organization_context_is_rejected_before_database_access(self):
        for value in (None, True, False, 0, -1, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OrganizationRepository(Mock(), value)

    def test_scoped_factory_has_separate_immutable_context_per_instance(self):
        legacy = PostgresPlatformRepository(Mock())
        first = legacy.for_organization(1)
        second = legacy.for_organization(2)
        self.assertEqual(first.organization_id, 1)
        self.assertEqual(second.organization_id, 2)
        self.assertIsNot(first, second)
        with self.assertRaises(AttributeError):
            first.organization_id = 2

    def test_legacy_jobs_adapter_cannot_bypass_quarantine(self):
        with self.assertRaisesRegex(RuntimeError, "no verified business ownership"):
            PostgresJobRepository(Mock())

    def test_user_supplied_table_and_ownership_fields_are_rejected(self):
        repository = OrganizationRepository(Mock(), 1)
        with self.assertRaises(ValueError):
            repository.fetch_record("users", 1)
        with self.assertRaises(ValueError):
            repository.update_record("nutrition_plans", 1, {"client_id": 2})
        with self.assertRaises(ValueError):
            repository.create_client(coach_id=1, payload={"organization_id": 2})


if __name__ == "__main__":
    unittest.main()
