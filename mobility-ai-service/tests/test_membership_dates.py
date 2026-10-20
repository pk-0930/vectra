import unittest
from datetime import date
from services.membership_service import add_months


class MembershipDateTests(unittest.TestCase):
    def test_calendar_boundaries_clamp_without_overflow(self):
        cases = [(date(2024, 1, 31), 1, date(2024, 2, 29)),
                 (date(2025, 1, 31), 1, date(2025, 2, 28)),
                 (date(2024, 2, 29), 12, date(2025, 2, 28)),
                 (date(2026, 11, 30), 3, date(2027, 2, 28)),
                 (date(2026, 12, 15), 6, date(2027, 6, 15))]
        for start, months, expected in cases:
            with self.subTest(start=start, months=months):
                self.assertEqual(add_months(start, months), expected)
