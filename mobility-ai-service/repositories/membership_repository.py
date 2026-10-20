"""Tenant-scoped manual payment ledger; caller owns the transaction."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from repositories.gym_repository import GymRepository


class MembershipRepository(GymRepository):
    def lock(self, access, identifier, admin=False):
        db, org = access.connection, access.organization_id
        # Serialize gym confirmations, renewals and reference checks without upgrading
        # the relationship SHARE locks held by request authorization.
        self.profile(db, org, lock=True)
        return db.execute('SELECT * FROM gym_pending_purchases WHERE organization_id=%s AND id=%s ' +
                          ('' if admin else 'AND relationship_id=%s ') + 'FOR UPDATE',
                          (org, identifier) if admin else (org, identifier, access.context['id'])).fetchone()

    def event(self, access, purchase, kind, details, evidence=None):
        access.connection.execute('INSERT INTO gym_payment_events(organization_id,purchase_id,actor_user_id,kind,details,evidence) VALUES(%s,%s,%s,%s,%s,%s)',
                                  (access.organization_id, purchase, access.user_id, kind, Jsonb(details), evidence))

    def status(self, access, purchase, status):
        access.connection.execute('UPDATE gym_pending_purchases SET status=%s WHERE organization_id=%s AND id=%s',
                                  (status, access.organization_id, purchase))

    def notice(self, db, org, relationship, key, subject, message):
        recipient = db.execute('SELECT u.email FROM users u JOIN organization_relationships r ON r.user_id=u.id WHERE r.organization_id=%s AND r.id=%s', (org, relationship)).fetchone()
        notice = db.execute('INSERT INTO billing_notifications(id,organization_id,recipient,event_key,subject,message) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id',
                            (uuid4(), org, recipient['email'], key, subject, message)).fetchone()
        if notice:
            db.execute('INSERT INTO email_outbox(id,billing_notification_id) VALUES(%s,%s)', (uuid4(), notice['id']))

    def details(self, access, identifier, admin=False):
        row = access.connection.execute('SELECT * FROM gym_pending_purchases WHERE organization_id=%s AND id=%s' +
                                        ('' if admin else ' AND relationship_id=%s'),
                                        (access.organization_id, identifier) if admin else (access.organization_id, identifier, access.context['id'])).fetchone()
        if not row:
            return None
        db, org = access.connection, access.organization_id
        events = db.execute('SELECT id,kind,details,actor_user_id,created_at,evidence IS NOT NULL AS has_evidence FROM gym_payment_events WHERE organization_id=%s AND purchase_id=%s ORDER BY id', (org, identifier)).fetchall()
        period = db.execute('SELECT *, CASE WHEN revoked_at IS NOT NULL THEN \'revoked\' WHEN starts_on>(now() AT TIME ZONE \'Asia/Kolkata\')::date THEN \'scheduled\' WHEN ends_before<=(now() AT TIME ZONE \'Asia/Kolkata\')::date THEN \'expired\' ELSE \'active\' END AS status FROM gym_membership_periods WHERE organization_id=%s AND purchase_id=%s', (org, identifier)).fetchone()
        payment = db.execute('SELECT * FROM gym_verified_payments WHERE organization_id=%s AND purchase_id=%s', (org, identifier)).fetchone()
        pt_state = db.execute('SELECT * FROM pt_purchase_states WHERE organization_id=%s AND purchase_id=%s', (org, identifier)).fetchone()
        pt = db.execute('SELECT * FROM pt_entitlements WHERE organization_id=%s AND purchase_id=%s', (org, identifier)).fetchone()
        return {'purchase': row, 'events': events, 'membership': period, 'payment': payment, 'pt_state': pt_state, 'pt': pt}
