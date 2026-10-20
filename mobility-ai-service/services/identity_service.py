"""Email ownership proofs and narrowly scoped, single-use staff invitations."""
import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from repositories.access_repository import AccessDenied, AccessRepository

GENERIC_MESSAGE = 'If the account is eligible, an email will arrive shortly.'
INVALID_LINK = 'This link is invalid, expired, revoked or already used.'


class IdentityService:
    def __init__(self, repository, security):
        self.repository = repository
        self.security = security

    @staticmethod
    def normalize_email(email):
        email = email.strip().lower()
        if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Enter a valid email address.')
        return email

    def token(self, action_id):
        # Domain separation from session signing. Rotation invalidates pending links.
        signature = hmac.new(self.security.config.token_secret.encode(),
                             f'vectra-email-v1:{action_id}'.encode(), hashlib.sha256).hexdigest()
        return f'{action_id}.{signature}'

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def rate_limit(self, key):
        digest = self.digest(key)
        with self.repository.transaction() as db:
            row = self.repository.increment_request_bucket(db, (digest,))
        return row['requests'] <= 20

    def enqueue(self, db, *, kind, email, user=None, organization_id=None, invited_by=None, role=None, return_gym_public_id=None, client_id=None):
        action_id = uuid4()
        lifetime = {'verify': timedelta(hours=24), 'recover': timedelta(minutes=30),
                    'invite': timedelta(days=3)}[kind]
        values = (action_id, kind, email, user['id'] if user else None, organization_id, invited_by,
             role, self.digest(self.token(action_id)), user.get('session_version', 0) if user else None,
             datetime.now(UTC) + lifetime)
        if client_id is not None:
            self.repository.insert_client_action(db, values, client_id)
        else:
            self.repository.insert_action(db, values)
        if return_gym_public_id:
            self.repository.set_gym_return(db, action_id, return_gym_public_id)
        self.repository.insert_delivery(db, (uuid4(), action_id))
        return action_id

    def request_email(self, email, kind):
        email = self.normalize_email(email)
        if kind not in {'verify', 'recover'}:
            raise ValueError('Unsupported email request.')
        with self.repository.transaction() as db:
            # Serialize cooldown and issuance across API processes.
            self.repository.lock_recipient(db, (email,))
            recent = self.repository.recent_action(db, (email, kind))
            user = self.repository.lock_user_by_email(db, (email,))
            if not recent and user and (kind == 'recover' or not user['email_verified_at']):
                origin = self.repository.last_gym_return(db, user['id']) if kind == 'verify' else None
                self.enqueue(db, kind=kind, email=email, user=user,
                             return_gym_public_id=origin['return_gym_public_id'] if origin else None)
        return {'message': GENERIC_MESSAGE}

    def register_coach(self, payload):
        email = self.normalize_email(payload['email'])
        if not 12 <= len(payload['password']) <= 256:
            raise ValueError('Use a password between 12 and 256 characters.')
        password_hash = self.security.hash_password(payload['password'])
        profile = payload['coach']
        with self.repository.transaction() as db:
            self.repository.lock_recipient(db, (email,))
            if self.repository.find_user_id(db, (email,)):
                raise ValueError('Unable to register. Sign in or recover your existing account.')
            user = self.repository.insert_identity(db, (email, password_hash))
            coach = self.repository.insert_coach_profile(db, (user['id'], profile['first_name'].strip(), profile['last_name'].strip(), profile.get('dob'),
                 profile.get('gender'), profile.get('mobile'), profile.get('years_of_experience', 0),
                 profile.get('associated_gym'), profile.get('clients_trained', 0)))
            self.repository.provision_coach_business(db, (coach['id'],))
            self.enqueue(db, kind='verify', email=email, user=user)
        return user, coach

    def register_member(self, payload):
        email = self.normalize_email(payload['email'])
        if not 12 <= len(payload['password']) <= 256:
            raise ValueError('Use a password between 12 and 256 characters.')
        hashed = self.security.hash_password(payload['password'])
        with self.repository.transaction() as db:
            self.repository.lock_recipient(db, (email,))
            if self.repository.find_user_id(db, (email,)):
                raise ValueError('Unable to register. Sign in or recover your existing account.')
            user = self.repository.insert_identity(db, (email, hashed))
            self.enqueue(db, kind='verify', email=email, user=user, return_gym_public_id=payload.get('public_id'))
        return user

    def register_business(self, payload):
        from repositories.billing_repository import BillingRepository
        email = self.normalize_email(payload['email'])
        if not 12 <= len(payload['password']) <= 256:
            raise ValueError('Use a password between 12 and 256 characters.')
        name = payload['business_name'].strip()
        if not 1 <= len(name) <= 120 or payload['business_type'] not in {'gym', 'coaching'}:
            raise ValueError('Enter a business name and type.')
        hashed = self.security.hash_password(payload['password'])
        with self.repository.transaction() as db:
            self.repository.lock_recipient(db, (email,))
            if self.repository.find_user_id(db, (email,)):
                raise ValueError('Unable to register. Sign in or recover your existing account.')
            user = self.repository.insert_identity(db, (email, hashed))
            BillingRepository(self.repository.config).create_business(
                db, user['id'], payload['request_id'], name, payload['business_type'])
            self.enqueue(db, kind='verify', email=email, user=user)
        return user

    def create_invitation(self, access, email, role, client_id=None):
        access.require_admin()
        if role not in {'trainer', 'admin', 'client'} or (role == 'admin' and 'owner' not in access.roles):
            raise AccessDenied('Only owners may invite admins. Owners cannot be invited here.')
        if role == 'client':
            if type(client_id) is not int or client_id <= 0:
                raise ValueError('Choose the coaching profile to invite.')
            client = access.require_client(client_id, staff=True)
            if client.get('organization_relationship_id') or not client['is_active']:
                raise ValueError('Only active, unlinked coaching profiles can be invited.')
        elif client_id is not None:
            raise ValueError('Only client invitations can link a coaching profile.')
        email = self.normalize_email(email)
        db = access.connection
        self.repository.lock_recipient(db, (f'invite:{access.organization_id}:{email}',))
        recent = self.repository.recent_invitation(db, (access.organization_id, email))
        if recent:
            raise ValueError('Please wait one minute before sending another invitation.')
        self.repository.revoke_prior_invitations(db, (access.organization_id, email, role))
        self.enqueue(db, kind='invite', email=email, organization_id=access.organization_id,
                     invited_by=access.user_id, role=role, client_id=client_id)
        return {'message': 'Invitation queued. It expires in 3 days.'}

    def list_invitations(self, access):
        access.require_admin()
        return self.repository.invitation_summaries(access.connection, (access.organization_id,))

    def revoke_invitation(self, access, action_id):
        access.require_admin()
        row = self.repository.lock_invitation(access.connection, (action_id, access.organization_id))
        if not row or (row['role'] == 'admin' and 'owner' not in access.roles):
            raise AccessDenied('Invitation cannot be revoked by this account.')
        self.repository.revoke_invitation(access.connection, (action_id,))
        return {'message': 'Invitation revoked.'}

    def consume(self, token, kind, *, password=None, email=None, current_user=None):
        if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f-]{36}\.[0-9a-f]{64}', token):
            raise ValueError(INVALID_LINK)
        try:
            action_id = UUID(token.split('.')[0])
        except (ValueError, AttributeError):
            raise ValueError(INVALID_LINK) from None
        if kind not in {'verify', 'recover', 'invite'} or not hmac.compare_digest(token, self.token(action_id)):
            raise ValueError(INVALID_LINK)
        if password is not None and not 12 <= len(password) <= 256:
            raise ValueError('Use a password between 12 and 256 characters.')
        password_hash = self.security.hash_password(password) if password else None
        with self.repository.transaction() as db:
            action = self.repository.lock_action(db, (action_id,))
            if (not action or action['kind'] != kind or action['consumed_at'] or action['revoked_at']
                    or action['expires_at'] <= datetime.now(UTC)
                    or not hmac.compare_digest(action['token_hash'], self.digest(token))):
                raise ValueError(INVALID_LINK)
            if kind == 'invite':
                self._accept_invitation(db, action, email, password_hash, current_user)
            else:
                user = self.repository.lock_identity(db, (action['user_id'],))
                if not user or user['email'] != action['email'] or user['session_version'] != action['session_version']:
                    raise ValueError(INVALID_LINK)
                if kind == 'recover':
                    if not password_hash:
                        raise ValueError('A new password is required.')
                    self.repository.reset_password(db, (password_hash, user['id']))
                else:
                    self.repository.verify_identity(db, (user['id'],))
            self.repository.consume_action(db, (action_id,))
        return {'message': 'Password updated. Sign in again on every device.' if kind == 'recover'
                else 'Invitation accepted. Sign in to open your business.' if kind == 'invite' else 'Email verified. Continue to your workspace.'}

    def _accept_invitation(self, db, action, email, password_hash, current_user):
        if self.normalize_email(email or '') != action['email']:
            raise ValueError('Sign in with the email address this invitation was sent to.')
        # Revalidate inviter privileges at acceptance, including already-issued links.
        inviter = AccessRepository(db, action['organization_id'], action['invited_by'])
        inviter.require_admin()
        if action['role'] == 'admin' and 'owner' not in inviter.roles:
            raise AccessDenied('The invitation issuer no longer has permission.')
        self.repository.lock_recipient(db, (action['email'],))
        user = self.repository.lock_user_by_email(db, (action['email'],))
        if user:
            if not current_user or current_user['id'] != user['id'] or current_user.get('session_version', 0) != user['session_version']:
                raise ValueError('Sign in with the email address this invitation was sent to.')
        else:
            if current_user:
                raise ValueError('Sign out before creating the invited account.')
            if not password_hash:
                raise ValueError('Create a password for your new account, or sign in if you already have one.')
            user = self.repository.insert_identity(db, (action['email'], password_hash))
        relationship = self.repository.ensure_relationship(db, (action['organization_id'], user['id']))
        if relationship['status'] != 'active':
            raise AccessDenied('This business relationship is inactive. Contact the owner.')
        if action['role'] == 'client':
            self.repository.claim_client(db, action['organization_id'], action['client_id'], relationship['id'])
        else:
            self.repository.grant_invited_role(db, (action['organization_id'], relationship['id'], action['role']))
        self.repository.verify_invitee(db, (user['id'],))
