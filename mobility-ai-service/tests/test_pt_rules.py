from datetime import date, timedelta
import unittest
from services.pt_service import coverage_end, appointment_time


class PtRuleTests(unittest.TestCase):
    def test_contiguous_membership_coverage_and_gap(self):
        start = date(2026, 10, 20)
        periods = [{'starts_on': start-timedelta(days=10), 'ends_before': start+timedelta(days=10)},
                   {'starts_on': start+timedelta(days=10), 'ends_before': start+timedelta(days=40)}]
        self.assertEqual(coverage_end(periods, start), start+timedelta(days=40))
        periods[1]['starts_on'] += timedelta(days=1)
        self.assertEqual(coverage_end(periods, start), start+timedelta(days=10))

    def test_appointments_require_offset_and_normalize_to_utc(self):
        result = appointment_time('2026-10-20T10:00:00+05:30')
        self.assertEqual(result.hour, 4)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.utcoffset(), timedelta(0))
        for value in [None, '', '2026-10-20T10:00:00', '2026-02-30T10:00:00Z']:
            with self.subTest(value=value), self.assertRaises(ValueError): appointment_time(value)

