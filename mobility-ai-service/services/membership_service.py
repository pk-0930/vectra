"""Manual receipt verification, fixed-calendar memberships and auditable exceptions."""
import calendar
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from repositories.access_repository import AccessDenied, ResourceNotFound
from services.gym_service import GymService, clean_image


def today_india():
    return datetime.now(ZoneInfo('Asia/Kolkata')).date()


def add_months(start, months):
    index = start.year * 12 + start.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(start.day, calendar.monthrange(year, month + 1)[1]))


class MembershipService:
    def __init__(self, repository):
        self.repository = repository

    def require(self, access, admin=False):
        if access.context['organization_type'] != 'gym':
            raise AccessDenied('Gym membership access is required.')
        if admin:
            GymService.require_admin(access)

    def details(self, access, identifier, admin=False):
        self.require(access, admin)
        result = self.repository.details(access, identifier, admin)
        if not result:
            raise ResourceNotFound('Purchase not found.')
        return result

    def evidence(self, access, identifier, raw):
        self.require(access)
        png = clean_image(raw)
        row = self.repository.lock(access, identifier)
        if not row:
            raise ResourceNotFound('Purchase not found.')
        if row['status'] not in {'pending', 'rejected', 'awaiting_verification'}:
            raise ValueError('This purchase no longer accepts evidence.')
        count = access.connection.execute('SELECT count(*) AS n FROM gym_payment_events WHERE organization_id=%s AND purchase_id=%s AND kind=\'evidence\'', (access.organization_id, identifier)).fetchone()['n']
        if count >= 5:
            raise ValueError('Evidence limit reached. Contact reception for corrections.')
        self.repository.event(access, identifier, 'evidence', {}, png)
        return {'uploaded': True}

    def act(self, access, identifier, action, payload, admin=False):
        self.require(access, admin)
        allowed = {'confirm', 'reject', 'cancel', 'refund', 'correct'} if admin else {'submit', 'cancel'}
        if action not in allowed:
            raise AccessDenied('This payment action is unavailable.')
        repo, db, org = self.repository, access.connection, access.organization_id
        row = repo.lock(access, identifier, admin)
        if not row:
            raise ResourceNotFound('Purchase not found.')
        if action == 'confirm' and row['status'] == 'confirmed':
            return self.details(access, identifier, admin)
        note = str(payload.get('note', '')).strip()
        if not note or len(note) > 2000:
            raise ValueError('Enter a reason or receipt verification note (up to 2000 characters).')
        if action == 'confirm':
            if row['status'] not in {'pending', 'awaiting_verification'}:
                raise ValueError('Only pending or submitted purchases can be confirmed.')
            if payload.get('receipt_checked') is not True:
                raise ValueError('Verify actual bank/merchant receipt or personally received cash first.')
            method = payload.get('method')
            reference = str(payload.get('reference', '')).strip().upper()
            if method not in {'cash', 'upi'} or not re.fullmatch(r'[A-Z0-9][A-Z0-9._/-]{2,119}', reference):
                raise ValueError('Enter UPI transaction reference or a unique cash receipt number (3–120 characters).')
            amount = payload.get('amount_paise')
            if type(amount) is not int or amount != row['amount_paise']:
                raise ValueError('Actual receipt must equal the immutable purchase amount. Resolve incorrect amounts externally before confirmation.')
            try:
                received = date.fromisoformat(payload.get('received_on', ''))
                requested = date.fromisoformat(payload['starts_on']) if payload.get('starts_on') else today_india()
            except (TypeError, ValueError):
                raise ValueError('Enter valid receipt and start dates.') from None
            today = today_india()
            if received > today or received < row['created_at'].astimezone(ZoneInfo('Asia/Kolkata')).date() or requested < today:
                raise ValueError('Receipt must be dated between purchase creation and today; membership cannot be backdated.')
            if db.execute('SELECT 1 FROM gym_verified_payments WHERE organization_id=%s AND reference=%s', (org, reference)).fetchone():
                raise ValueError('This transaction or cash receipt reference has already been used in this gym.')
            relationship = db.execute("SELECT id FROM organization_relationships WHERE organization_id=%s AND id=%s AND status='active' FOR SHARE", (org, row['relationship_id'])).fetchone()
            if not relationship:
                raise ValueError('The member relationship is inactive.')
            from repositories.pt_repository import PtRepository
            from services.pt_service import PtService
            pt_service = PtService(PtRepository(repo.config))
            prepared = pt_service.prepare_confirmation(access, row, requested, payload.get('pt_terms_consent', False))
            if prepared and prepared.get('error'):
                repo.event(access, identifier, 'correction', {'resolution_required': prepared['error'], 'receipt_report': payload})
                return self.details(access, identifier, admin) | {'resolution_error': prepared['error']}
            gym_plan = next((p for p in row['snapshot']['plans'] if p['kind'] == 'gym'), None)
            end = db.execute('SELECT max(ends_before) AS end FROM gym_membership_periods WHERE organization_id=%s AND relationship_id=%s AND revoked_at IS NULL', (org, row['relationship_id'])).fetchone()['end']
            start = max(requested, end) if end else requested
            finish = add_months(start, gym_plan['duration_months']) if gym_plan else None
            db.execute('INSERT INTO gym_verified_payments(purchase_id,organization_id,method,reference,amount_paise,received_on,verifier_user_id) VALUES(%s,%s,%s,%s,%s,%s,%s)', (identifier, org, method, reference, amount, received, access.user_id))
            if gym_plan:
                db.execute('INSERT INTO gym_membership_periods(purchase_id,organization_id,relationship_id,starts_on,ends_before) VALUES(%s,%s,%s,%s,%s)', (identifier, org, row['relationship_id'], start, finish))
            if prepared:
                pt_service.activate(access, row, prepared)
            repo.status(access, identifier, 'confirmed')
            repo.event(access, identifier, 'confirmed', {**payload, 'reference': reference, 'starts_on': str(start), 'ends_before': str(finish)})
            repo.notice(db, org, row['relationship_id'], f'membership-confirmed:{identifier}', 'Gym membership confirmed', f'Your gym/PT payment has been verified. ' + (f'Membership starts {start} and ends before {finish}. ' if gym_plan else '') + (f'PT starts {prepared["start"]} and ends before {prepared["finish"]}. ' if prepared else '') + 'Fixed duration; renew manually.')
        elif action in {'submit', 'reject', 'cancel'}:
            if row['status'] not in {'pending', 'awaiting_verification', 'rejected'}:
                raise ValueError('This purchase cannot be changed in its current state.')
            if action == 'submit' and not str(payload.get('reference', '')).strip():
                raise ValueError('Enter your transaction reference or cash receipt details.')
            status = {'submit': 'awaiting_verification', 'reject': 'rejected', 'cancel': 'cancelled'}[action]
            repo.event(access, identifier, {'submit': 'submitted', 'reject': 'rejected', 'cancel': 'cancelled'}[action], payload)
            repo.status(access, identifier, status)
            if action in {'reject', 'cancel'}:
                db.execute('UPDATE pt_purchase_states SET reserved_until=now() WHERE organization_id=%s AND purchase_id=%s', (org, identifier))
        elif action == 'refund':
            if row['status'] == 'refunded':
                return self.details(access, identifier, admin)
            if row['status'] not in {'confirmed', 'pending', 'awaiting_verification', 'rejected'} or payload.get('external_refund_completed') is not True:
                raise ValueError('Record the completed external refund and its reference; no funds are transferred by Vectra.')
            if payload.get('amount_paise') != row['amount_paise'] or payload.get('entitlement') not in {'revoke', 'retain'} or not str(payload.get('reference', '')).strip():
                raise ValueError('Record the full refund amount, external reference and explicit revoke/retain entitlement decision.')
            if payload['entitlement'] == 'revoke':
                db.execute('UPDATE gym_membership_periods SET revoked_at=now() WHERE organization_id=%s AND purchase_id=%s', (org, identifier))
                db.execute('UPDATE pt_entitlements SET revoked_at=now() WHERE organization_id=%s AND purchase_id=%s', (org, identifier))
                db.execute("UPDATE coaching_appointments SET status='cancelled',version=version+1 WHERE organization_id=%s AND entitlement_id=%s AND status='booked'", (org, identifier))
            db.execute('UPDATE pt_purchase_states SET reserved_until=now(),resolution_reason=NULL WHERE organization_id=%s AND purchase_id=%s', (org, identifier))
            repo.event(access, identifier, 'refunded', payload)
            repo.status(access, identifier, 'refunded')
            repo.notice(db, org, row['relationship_id'], f'membership-refunded:{identifier}', 'Gym refund recorded', f'The gym recorded an external full refund. Membership consequence: {payload["entitlement"]}. Vectra did not transfer money.')
        else:
            repo.event(access, identifier, 'correction', {'note': note})
        return self.details(access, identifier, admin)

    def reminders(self):
        # No provider calls. Durable deduplicated notices use the existing email worker.
        with self.repository.transaction() as db:
            rows = db.execute("SELECT m.* FROM gym_membership_periods m JOIN organization_relationships r ON r.organization_id=m.organization_id AND r.id=m.relationship_id JOIN organizations o ON o.id=m.organization_id WHERE m.revoked_at IS NULL AND r.status='active' AND o.status='active' AND m.ends_before IN ((now() AT TIME ZONE 'Asia/Kolkata')::date+7,(now() AT TIME ZONE 'Asia/Kolkata')::date+1) AND NOT EXISTS(SELECT 1 FROM gym_membership_periods n WHERE n.organization_id=m.organization_id AND n.relationship_id=m.relationship_id AND n.revoked_at IS NULL AND n.starts_on<=m.ends_before AND n.ends_before>m.ends_before)").fetchall()
            for row in rows:
                self.repository.notice(db, row['organization_id'], row['relationship_id'], f'membership-expiry:{row["purchase_id"]}:{today_india()}', 'Gym membership expires soon', f'Your paid gym coverage ends before {row["ends_before"]}. Renew manually through your gym.')
            return len(rows)
