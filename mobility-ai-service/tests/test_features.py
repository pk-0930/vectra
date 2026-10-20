import unittest
from unittest.mock import patch
from config.features import analysis_enabled


class FeatureTests(unittest.TestCase):
    def test_disabled_by_default_and_only_explicit_true_enables(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertFalse(analysis_enabled())
        for value, expected in [('false', False), ('', False), ('1', False),
                                ('tru', False), ('true', True), (' TRUE ', True)]:
            with self.subTest(value=value), patch.dict('os.environ', {'FORM_ANALYSIS_ENABLED': value}):
                self.assertEqual(analysis_enabled(), expected)
