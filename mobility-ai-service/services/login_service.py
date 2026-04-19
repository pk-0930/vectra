class LoginService:
    def __init__(self):
        self._demo_username = "admin"
        self._demo_password = "admin"

    def authenticate(self, username: str, password: str):
        normalized_username = username.strip()
        normalized_password = password.strip()

        if (
            normalized_username == self._demo_username and
            normalized_password == self._demo_password
        ):
            return {
                "authenticated": True,
                "message": "Login successful.",
                "username": normalized_username,
            }

        return {
            "authenticated": False,
            "message": "Invalid credentials. Use admin / admin",
            "username": normalized_username,
        }
