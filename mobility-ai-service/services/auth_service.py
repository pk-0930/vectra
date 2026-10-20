from datetime import UTC, datetime

from config.postgres_config import get_postgres_config
from repositories.platform_repository import PostgresPlatformRepository
from services.security_service import SecurityService


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(self, repository=None, security_service=None):
        self.repository = repository or PostgresPlatformRepository(get_postgres_config())
        self.security_service = security_service or SecurityService()

    def sign_up_coach(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        dob=None,
        gender: str | None = None,
        mobile: str | None = None,
        years_of_experience: int = 0,
        associated_gym: str | None = None,
        clients_trained: int = 0,
    ) -> dict:
        from repositories.identity_repository import IdentityRepository
        from services.identity_service import IdentityService
        identity = IdentityService(IdentityRepository(self.repository.config), self.security_service)
        user, coach = identity.register_coach({
            'email': email, 'password': password,
            'coach': dict(first_name=first_name, last_name=last_name, dob=dob, gender=gender,
                          mobile=mobile, years_of_experience=years_of_experience,
                          associated_gym=associated_gym, clients_trained=clients_trained),
        })
        token = self.security_service.create_access_token(
            user_id=user['id'], email=user['email'], session_version=user['session_version'])
        return self._build_auth_payload(user, coach, token)

    def sign_in(self, *, email: str, password: str) -> dict:
        normalized_email = email.strip().lower()
        user = self.repository.fetch_user_by_email(normalized_email)
        if user is None or not self.security_service.verify_password(password, user["password_hash"]):
            raise ValueError("Invalid email or password.")

        coach = self.repository.fetch_coach_by_user_id(user["id"])
        token = self.security_service.create_access_token(user_id=user["id"], email=user["email"], session_version=user.get("session_version", 0))
        return self._build_auth_payload(user, coach, token)

    def get_authenticated_user(self, token: str) -> dict | None:
        payload = self.security_service.decode_access_token(token)
        if payload is None:
            return None

        user = self.repository.fetch_user_by_id(payload["sub"])
        if user is None or payload.get("ver", 0) != user.get("session_version", 0):
            return None

        coach = self.repository.fetch_coach_by_user_id(user["id"])
        return {
            "user": user,
            "coach": coach,
            "organizations": self.repository.list_user_organizations(user["id"]),
        }

    def session_response(self, auth_context: dict) -> dict:
        return self._build_auth_payload(
            auth_context["user"], auth_context["coach"], "",
            organizations=auth_context["organizations"],
        )

    def _build_auth_payload(
        self, user: dict, coach: dict | None, token: str,
        organizations: list[dict] | None = None,
    ) -> dict:
        return {
            "access_token": token,
            "token_type": "bearer",
            "organizations": (self.repository.list_user_organizations(user["id"])
                              if organizations is None else organizations),
            "user": {
                "id": user["id"],
                "email": user["email"],
                "email_verified": bool(user.get("email_verified_at")),
                "verification_required": user.get("verification_required", False),
            },
            "coach": {
                "id": coach["id"],
                "user_id": coach["user_id"],
                "first_name": coach["first_name"],
                "last_name": coach["last_name"],
                "dob": coach["dob"].isoformat() if coach["dob"] else None,
                "gender": coach["gender"],
                "mobile": coach["mobile"],
                "years_of_experience": coach["years_of_experience"],
                "associated_gym": coach["associated_gym"],
                "clients_trained": coach["clients_trained"],
            }
            if coach
            else None,
        }
