from datetime import UTC, datetime
from uuid import uuid4
from psycopg.types.json import Jsonb
from repositories.identity_repository import IdentityRepository
from repositories.access_repository import AccessRepository, AccessDenied


class BillingRepository(IdentityRepository):
    def authorize(self, db, organization_id, user_id, owner=False):
        access = AccessRepository(db, organization_id, user_id)
        if owner and 'owner' not in access.roles:
            raise AccessDenied('Only business owners can manage software billing.')
        return access

    def organization(self, db, organization_id, lock=False):
        return db.execute('SELECT * FROM organizations WHERE id=%s' + (' FOR UPDATE' if lock else ''), (organization_id,)).fetchone()

    def create_business(self, db, user_id, request_id, name, kind):
        self.lock_recipient(db, (f'onboarding:{user_id}:{request_id}',))
        previous = db.execute('SELECT * FROM business_onboarding_requests WHERE user_id=%s AND request_id=%s',
                              (user_id, request_id)).fetchone()
        if previous:
            if previous['name'] != name or previous['business_type'] != kind:
                raise ValueError('This onboarding request was already used with different details.')
            return previous['organization_id']
        org = db.execute('INSERT INTO organizations(name,organization_type) VALUES(%s,%s) RETURNING id', (name, kind)).fetchone()['id']
        rel = db.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,%s) RETURNING id', (org, user_id)).fetchone()['id']
        db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'owner')", (org, rel))
        db.execute('INSERT INTO business_onboarding_requests(user_id,request_id,organization_id,name,business_type) VALUES(%s,%s,%s,%s,%s)',
                   (user_id, request_id, org, name, kind))
        return org

    def subscriptions(self, db, org, mode):
        return db.execute('SELECT * FROM software_subscriptions WHERE organization_id=%s AND mode=%s ORDER BY created_at DESC', (org, mode)).fetchall()

    def payments(self, db, org, mode):
        return db.execute('SELECT p.*,s.plan_snapshot FROM software_payments p JOIN software_subscriptions s ON s.id=p.subscription_id '
                          'WHERE p.organization_id=%s AND p.mode=%s ORDER BY p.period_end DESC', (org, mode)).fetchall()

    def insert_subscription(self, db, org, user_id, config, plan, start_at):
        return db.execute('INSERT INTO software_subscriptions(id,organization_id,requested_by,mode,plan_snapshot,terms_version,start_at) '
                          'VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                          (uuid4(), org, user_id, config.mode, Jsonb(plan), config.terms_version, start_at)).fetchone()

    def request_cancel(self, db, subscription):
        db.execute('UPDATE software_subscriptions SET cancel_requested=true,next_sync_at=now() WHERE id=%s', (subscription['id'],))

    def schedule_sync(self, db, subscription):
        db.execute('UPDATE software_subscriptions SET next_sync_at=LEAST(next_sync_at,now()) WHERE id=%s', (subscription['id'],))

    def record_webhook(self, mode, event_id, digest, event, provider_id):
        with self.transaction() as db:
            row = db.execute('INSERT INTO software_webhook_events(mode,event_id,body_hash,event_type,provider_subscription_id,status) '
                              'VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id',
                              (mode, event_id, digest, event, provider_id, 'pending' if provider_id else 'ignored')).fetchone()
            if not row:
                old = db.execute('SELECT body_hash FROM software_webhook_events WHERE mode=%s AND event_id=%s', (mode, event_id)).fetchone()
                if old['body_hash'] != digest: raise ValueError('Conflicting webhook event identity.')
            if provider_id:
                db.execute('UPDATE software_subscriptions SET next_sync_at=now() WHERE mode=%s AND provider_id=%s', (mode, provider_id))

    def claim_work(self, mode):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM software_subscriptions WHERE mode=%s AND next_sync_at<=now() "
                              "AND (lease_until IS NULL OR lease_until<now()) AND status<>'creation_failed' AND NOT (status='cancelled' AND provider_id IS NULL) "
                              'ORDER BY next_sync_at FOR UPDATE SKIP LOCKED LIMIT 1', (mode,)).fetchone()
            if not row: return None
            row['lease_token'] = uuid4()
            row['sync_started_at'] = datetime.now(UTC)
            db.execute("UPDATE software_subscriptions SET lease_token=%s,lease_until=now()+interval '5 minutes',"
                       "status=CASE WHEN status='queued' THEN 'creating' ELSE status END WHERE id=%s", (row['lease_token'], row['id']))
            return row

    def lock_claim(self, db, row):
        return db.execute('SELECT * FROM software_subscriptions WHERE id=%s AND lease_token=%s FOR UPDATE',
                          (row['id'], row['lease_token'])).fetchone()

    def finish_sync(self, db, row, remote, cancel_confirmed):
        terminal = remote['status'] in {'cancelled','completed','expired'}
        db.execute("UPDATE software_subscriptions SET provider_id=%s,customer_id=%s,status=%s,cancel_confirmed=%s,"
                   "closed_at=CASE WHEN %s THEN COALESCE(closed_at,now()) ELSE NULL END,updated_at=now(),"
                   "next_sync_at=now()+interval '15 minutes',lease_token=NULL,lease_until=NULL,failures=0,error_code=NULL WHERE id=%s",
                   (remote['id'], remote.get('customer_id'), remote['status'], cancel_confirmed, terminal, row['id']))
        db.execute("UPDATE software_webhook_events SET status='processed',processed_at=now() WHERE mode=%s "
                   "AND provider_subscription_id=%s AND status='pending' AND received_at<=%s", (row['mode'], remote['id'], row['sync_started_at']))

        db.execute("UPDATE software_subscriptions s SET next_sync_at=now() WHERE s.id=%s AND "
                   "((s.cancel_requested AND NOT s.cancel_confirmed) OR EXISTS(SELECT 1 FROM software_webhook_events e "
                   "WHERE e.mode=s.mode AND e.provider_subscription_id=s.provider_id AND e.status='pending'))", (row['id'],))

    def fail_sync(self, row, code, definitive=False):
        with self.transaction() as db:
            current = self.lock_claim(db, row)
            if not current: return
            status = current['status']
            if not current['provider_id']:
                status = 'creation_failed' if definitive else 'creation_unknown'
            attempts = current['failures'] + 1
            db.execute('UPDATE software_subscriptions SET status=%s,error_code=%s,failures=%s,lease_token=NULL,lease_until=NULL,'
                       "closed_at=CASE WHEN %s THEN now() ELSE closed_at END,next_sync_at=now()+(%s*interval '1 second') WHERE id=%s",
                       (status, code, attempts, status == 'creation_failed', min(3600, 30 * 2 ** min(attempts, 7)), row['id']))

    def upsert_payment(self, db, row, payment):
        old = db.execute('SELECT * FROM software_payments WHERE mode=%s AND (payment_id=%s OR invoice_id=%s) FOR UPDATE',
                          (row['mode'], payment['payment_id'], payment['invoice_id'])).fetchone()
        if old:
            fields = ['payment_id','invoice_id','amount_paise','currency','period_start','period_end','paid_at']
            if old['subscription_id'] != row['id'] or any(old[k] != payment[k] for k in fields):
                raise ValueError('Conflicting verified payment history.')
            # Refund totals never decrease on retries or stale responses.
            db.execute('UPDATE software_payments SET refunded_paise=GREATEST(refunded_paise,%s),verified_at=now() '
                       'WHERE mode=%s AND payment_id=%s', (payment['refunded_paise'], row['mode'], payment['payment_id']))
            return False
        db.execute('INSERT INTO software_payments(mode,payment_id,invoice_id,organization_id,subscription_id,amount_paise,'
                   'refunded_paise,currency,period_start,period_end,paid_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                   (row['mode'], payment['payment_id'], payment['invoice_id'], row['organization_id'], row['id'],
                    payment['amount_paise'], payment['refunded_paise'], payment['currency'], payment['period_start'],
                    payment['period_end'], payment['paid_at']))
        return True

    def cancel_uncreated(self, row):
        with self.transaction() as db:
            current = self.lock_claim(db, row)
            if current:
                db.execute("UPDATE software_subscriptions SET status='cancelled',cancel_confirmed=true,closed_at=now(),"
                           "lease_token=NULL,lease_until=NULL,next_sync_at=now() WHERE id=%s", (row['id'],))

    def notify_owners(self, db, org, key, subject, message):
        owners = db.execute("SELECT u.email FROM users u JOIN organization_relationships r ON r.user_id=u.id "
                            "WHERE r.organization_id=%s AND r.status='active' AND EXISTS(SELECT 1 FROM organization_staff_roles s "
                            "WHERE s.relationship_id=r.id AND s.role='owner' AND s.revoked_at IS NULL)", (org,)).fetchall()
        for owner in owners:
            notice = db.execute('INSERT INTO billing_notifications(id,organization_id,recipient,event_key,subject,message) '
                                 'VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id',
                                 (uuid4(), org, owner['email'], key, subject, message)).fetchone()
            if notice:
                db.execute('INSERT INTO email_outbox(id,billing_notification_id) VALUES(%s,%s)', (uuid4(), notice['id']))

    def operator_report(self):
        with self.transaction() as db:
            return db.execute("SELECT id,organization_id,mode,status,error_code,failures,next_sync_at FROM software_subscriptions "
                              "WHERE error_code IS NOT NULL ORDER BY next_sync_at LIMIT 100").fetchall()
