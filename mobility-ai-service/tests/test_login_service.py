import unittest

from services.login_service import LoginService


class LoginServiceTests(unittest.TestCase):
    def test_authenticate_accepts_demo_credentials(self):
        service = LoginService()

        result = service.authenticate("admin", "admin")

        self.assertTrue(result["authenticated"])
        self.assertEqual(result["username"], "admin")

    def test_authenticate_rejects_invalid_credentials(self):
        service = LoginService()

        result = service.authenticate("admin", "wrong-password")

        self.assertFalse(result["authenticated"])
        self.assertEqual(result["message"], "Invalid credentials. Use admin / admin")


if __name__ == "__main__":
    unittest.main()
