"""Transactional identity/outbox storage; no raw link tokens are persisted."""
from contextlib import contextmanager
from repositories.platform_repository import PostgresPlatformRepository


class IdentityRepository(PostgresPlatformRepository):
    def insert_client_action(self, connection, values, client_id):
        connection.execute(
            'INSERT INTO identity_actions(id,kind,email,user_id,organization_id,invited_by,role,token_hash,session_version,expires_at,client_id) '
            'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (*values, client_id))

    def claim_client(self, connection, organization_id, client_id, relationship_id):
        client = connection.execute('SELECT organization_relationship_id FROM clients WHERE organization_id=%s AND id=%s AND is_active FOR UPDATE',
                                    (organization_id, client_id)).fetchone()
        if not client or client['organization_relationship_id'] not in {None, relationship_id}:
            raise ValueError('This coaching profile is unavailable or already linked to another account.')
        other = connection.execute('SELECT id FROM clients WHERE organization_id=%s AND organization_relationship_id=%s AND id<>%s',
                                   (organization_id, relationship_id, client_id)).fetchone()
        if other:
            raise ValueError('This account already has a coaching profile in this business.')
        connection.execute('UPDATE clients SET organization_relationship_id=%s WHERE organization_id=%s AND id=%s',
                           (relationship_id, organization_id, client_id))

    @contextmanager
    def transaction(self):
        with self._connect() as connection:
            with connection.transaction():
                yield connection

    def claim_delivery(self, connection):
        return connection.execute(
            "SELECT e.*, a.kind, a.email, a.organization_id, a.role, a.expires_at, "
            "a.consumed_at, a.revoked_at, a.token_hash, a.return_gym_public_id, o.name AS business_name, n.recipient, n.subject, n.message "
            "FROM email_outbox e LEFT JOIN identity_actions a ON a.id=e.action_id "
            "LEFT JOIN organizations o ON o.id=a.organization_id LEFT JOIN billing_notifications n ON n.id=e.billing_notification_id "
            "WHERE e.status='pending' AND e.available_at<=now() "
            "ORDER BY e.available_at FOR UPDATE OF e SKIP LOCKED LIMIT 1"
        ).fetchone()

    def insert_action(self, connection, values):
        return connection.execute(
            'INSERT INTO '
            'identity_actions(id,kind,email,user_id,organization_id,invited_by,role,token_hash,session_version,expires_at) '
            'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            values,
        )

    def set_gym_return(self, connection, action_id, public_id):
        connection.execute('UPDATE identity_actions SET return_gym_public_id=%s WHERE id=%s', (public_id, action_id))

    def last_gym_return(self, connection, user_id):
        return connection.execute("SELECT return_gym_public_id FROM identity_actions WHERE user_id=%s "
                                  "AND kind='verify' AND return_gym_public_id IS NOT NULL ORDER BY created_at DESC LIMIT 1",
                                  (user_id,)).fetchone()

    def insert_delivery(self, connection, values):
        return connection.execute(
            'INSERT INTO email_outbox(id,action_id) VALUES(%s,%s)',
            values,
        )

    def lock_recipient(self, connection, values):
        return connection.execute(
            'SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
            values,
        )

    def revoke_prior_invitations(self, connection, values):
        return connection.execute(
            'UPDATE identity_actions SET revoked_at=now() WHERE organization_id=%s AND email=%s AND role=%s '
            "AND kind='invite' AND consumed_at IS NULL AND revoked_at IS NULL",
            values,
        )

    def grant_invited_role(self, connection, values):
        return connection.execute(
            'INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,%s) ON '
            'CONFLICT(organization_id,relationship_id,role) WHERE revoked_at IS NULL DO NOTHING',
            values,
        )

    def verify_invitee(self, connection, values):
        return connection.execute(
            'UPDATE users SET '
            'email_verified_at=COALESCE(email_verified_at,now()),verification_required=false WHERE id=%s',
            values,
        )

    def provision_coach_business(self, connection, values):
        return connection.execute(
            'SELECT ensure_coach_business(%s,false)',
            values,
        )

    def consume_action(self, connection, values):
        return connection.execute(
            'UPDATE identity_actions SET consumed_at=now() WHERE id=%s',
            values,
        )

    def recent_invitation(self, connection, values):
        return connection.execute(
            "SELECT id FROM identity_actions WHERE organization_id=%s AND email=%s AND kind='invite' AND "
            "created_at>now()-interval '1 minute'",
            values,
        ).fetchone()

    def lock_user_by_email(self, connection, values):
        return connection.execute(
            'SELECT * FROM users WHERE email=%s FOR UPDATE',
            values,
        ).fetchone()

    def ensure_relationship(self, connection, values):
        return connection.execute(
            'INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,%s) ON '
            'CONFLICT(organization_id,user_id) DO UPDATE SET user_id=EXCLUDED.user_id RETURNING *',
            values,
        ).fetchone()

    def increment_request_bucket(self, connection, values):
        return connection.execute(
            'INSERT INTO identity_request_limits(bucket_hash) VALUES(%s) ON CONFLICT(bucket_hash) DO UPDATE '
            "SET requests=CASE WHEN identity_request_limits.window_start < now()-interval '1 hour' THEN 1 "
            'ELSE identity_request_limits.requests+1 END, window_start=CASE WHEN '
            "identity_request_limits.window_start < now()-interval '1 hour' THEN now() ELSE "
            'identity_request_limits.window_start END RETURNING requests',
            values,
        ).fetchone()

    def recent_action(self, connection, values):
        return connection.execute(
            "SELECT id FROM identity_actions WHERE email=%s AND kind=%s AND created_at>now()-interval '1 "
            "minute' LIMIT 1",
            values,
        ).fetchone()

    def find_user_id(self, connection, values):
        return connection.execute(
            'SELECT id FROM users WHERE email=%s',
            values,
        ).fetchone()

    def insert_identity(self, connection, values):
        return connection.execute(
            'INSERT INTO users(email,password_hash,created_at,updated_at) VALUES(%s,%s,now(),now()) '
            'RETURNING *',
            values,
        ).fetchone()

    def insert_coach_profile(self, connection, values):
        return connection.execute(
            'INSERT INTO '
            'coaches(user_id,first_name,last_name,dob,gender,mobile,years_of_experience,associated_gym,clients_trained,created_at,updated_at) '
            'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now()) RETURNING *',
            values,
        ).fetchone()

    def lock_action(self, connection, values):
        return connection.execute(
            'SELECT * FROM identity_actions WHERE id=%s FOR UPDATE',
            values,
        ).fetchone()

    def reset_password(self, connection, values):
        return connection.execute(
            'UPDATE users SET password_hash=%s,session_version=session_version+1,updated_at=now() WHERE '
            'id=%s',
            values,
        )

    def verify_identity(self, connection, values):
        return connection.execute(
            'UPDATE users SET email_verified_at=now(),verification_required=false,updated_at=now() WHERE '
            'id=%s',
            values,
        )

    def lock_identity(self, connection, values):
        return connection.execute(
            'SELECT * FROM users WHERE id=%s FOR UPDATE',
            values,
        ).fetchone()

    def cancel_delivery(self, connection, values):
        return connection.execute(
            "UPDATE email_outbox SET status='cancelled',error_code=NULL WHERE id=%s",
            values,
        )

    def fail_rotated_key_delivery(self, connection, values):
        return connection.execute(
            "UPDATE email_outbox SET status='failed',error_code='signing_key_changed' WHERE id=%s",
            values,
        )

    def complete_delivery(self, connection, values):
        return connection.execute(
            "UPDATE email_outbox SET attempts=attempts+1,status='sent',sent_at=now(),error_code=NULL WHERE "
            'id=%s',
            values,
        )

    def retry_delivery(self, connection, values):
        return connection.execute(
            'UPDATE email_outbox SET '
            "attempts=%s,status=%s,error_code='provider_send_failed',available_at=now()+(%s * interval '1 "
            "second') WHERE id=%s",
            values,
        )

    def invitation_summaries(self, connection, values):
        return connection.execute(
            "SELECT a.id,a.email,a.role,a.expires_at,a.consumed_at,a.revoked_at,e.status AS delivery_status,"
            "e.attempts,e.error_code FROM identity_actions a JOIN email_outbox e ON e.action_id=a.id "
            "WHERE a.organization_id=%s AND a.kind='invite' ORDER BY a.created_at DESC LIMIT 100",
            values,
        ).fetchall()

    def lock_invitation(self, connection, values):
        return connection.execute(
            "SELECT role FROM identity_actions WHERE id=%s AND organization_id=%s AND kind='invite' FOR UPDATE",
            values,
        ).fetchone()

    def revoke_invitation(self, connection, values):
        connection.execute(
            'UPDATE identity_actions SET revoked_at=now() WHERE id=%s AND consumed_at IS NULL', values)
