"""Web-only workspace rules. Historical published content survives package expiry."""
from datetime import timedelta
from repositories.access_repository import AccessDenied
from repositories.web_workspace_repository import WebWorkspaceRepository
from services.membership_service import today_india


class WebWorkspaceService:
    def __init__(self, repository=None):
        self.repository = repository or WebWorkspaceRepository()

    def inbox(self, access, before=None, limit=30):
        return self.repository.inbox(access, before, limit)

    def ready(self, platform_repository):
        try:
            return self.repository.ready(platform_repository)
        except Exception:
            return False

    def mark_read(self, access, identifier):
        return self.repository.mark_read(access, identifier)

    def announce(self, access, identifier, audience, subject, message):
        access.require_admin()
        subject, message = subject.strip(), message.strip()
        if audience not in {'all', 'trainers', 'members', 'clients'} or not 1 <= len(subject) <= 160 or not 1 <= len(message) <= 4000:
            raise ValueError('Choose an audience and enter a subject (1–160) and message (1–4000 characters).')
        return self.repository.announce(access, identifier, audience, subject, message)

    def reports(self, access, start=None, end=None):
        access.require_admin()
        today = today_india()
        start, end = start or today.replace(day=1), end or today
        if start > end or end - start > timedelta(days=366):
            raise ValueError('Choose an ordered reporting interval of at most 367 days.')
        return self.repository.reports(access, start, end, today)

    def set_rollout(self, access, enabled):
        if 'owner' not in access.roles:
            raise AccessDenied('Only the owner can change purchase availability.')
        return self.repository.set_rollout(access, enabled)
