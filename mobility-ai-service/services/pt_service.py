"""Paid PT eligibility, bounded reservations, capacity and appointments."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
from repositories.access_repository import AccessDenied, ResourceNotFound
from services.membership_service import add_months, today_india

INDIA = ZoneInfo('Asia/Kolkata')
PT_TERMS = {'appointment_minutes': 60, 'duration_sessions_per_day': 1,
            'single_session_expiry_days': 30, 'reservation_hours': 24,
            'cancellation_consumes_session': False,
            'completion_consumes_session': True, 'reassignment_requires_consent': True}


def coverage_end(periods, start):
    end = start
    for period in periods:
        if period['starts_on'] <= end and period['ends_before'] > end:
            end = period['ends_before']
    return end


def appointment_time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        raise ValueError('Provide an appointment time with a timezone offset.') from None


class PtService:
    def __init__(self, repository):
        self.repository = repository

    def check(self, db, org, member, plan, start, purchase=None, trainer=None):
        trainer = trainer or plan['trainer_relationship_id']
        if not self.repository.trainer_active(db, org, trainer):
            raise ValueError('Trainer is unavailable. Admin must arrange a consented reassignment or external refund.')
        end = coverage_end(self.repository.coverage(db, org, member), start)
        finish = add_months(start, plan['duration_months']) if plan['duration_months'] else min(start + timedelta(days=30), end)
        if finish <= start or finish > end:
            raise ValueError(f'PT needs continuous paid gym coverage from {start} through the package end. Renew membership before paying or verifying PT.')
        clients = self.repository.capacity_members(db, org, trainer, purchase)
        if member not in clients and len(clients) >= 10:
            raise ValueError('Trainer has reached 10 clients/reservations. Retain any receipt for reassignment or external refund; do not request another payment.')
        return finish

    def options(self, access):
        if access.context['organization_type'] != 'gym':
            return {'plans': [], 'coverage': [], 'terms': PT_TERMS}
        repo, db, org = self.repository, access.connection, access.organization_id
        profile = repo.profile(db, org)
        plans = []
        for plan in (profile['configuration'].get('plans', []) if profile else []):
            if plan['kind'] != 'pt' or not plan['active']:
                continue
            reason = None
            try:
                finish = self.check(db, org, access.context['id'], plan, today_india())
            except ValueError as exc:
                reason, finish = str(exc), None
            plans.append({**plan, 'eligible': reason is None, 'reason': reason, 'ends_before': finish})
        return {'plans': plans, 'coverage': repo.coverage(db, org, access.context['id']), 'terms': PT_TERMS,
                'public_id': profile['public_id'] if profile else None}

    def prepare_confirmation(self, access, row, start, terms_consent=False):
        plan = next((p for p in row['snapshot']['plans'] if p['kind'] == 'pt'), None)
        if not plan:
            return None
        db, org, repo = access.connection, access.organization_id, self.repository
        state = repo.state(db, org, row['id'])
        trainer = state['trainer_relationship_id'] if state else plan['trainer_relationship_id']
        try:
            if 'pt_service_terms' not in row['snapshot'] and terms_consent is not True:
                raise ValueError('This legacy PT purchase predates the session rules. Record member consent to the current PT service terms before activation.')
            finish = self.check(db, org, row['relationship_id'], plan, start, row['id'], trainer)
        except ValueError as exc:
            if not state:
                repo.reserve(db, row, trainer)
            db.execute('UPDATE pt_purchase_states SET reserved_until=now(),resolution_reason=%s WHERE organization_id=%s AND purchase_id=%s', (str(exc), org, row['id']))
            return {'error': str(exc)}
        return {'trainer': trainer, 'start': start, 'finish': finish, 'sessions': plan['sessions']}

    def activate(self, access, row, prepared):
        repo, db, org = self.repository, access.connection, access.organization_id
        client = repo.ensure_client(access, row)
        db.execute('INSERT INTO pt_entitlements(purchase_id,organization_id,member_relationship_id,trainer_relationship_id,client_id,starts_on,ends_before,remaining_sessions,service_terms) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)', (row['id'], org, row['relationship_id'], prepared['trainer'], client, prepared['start'], prepared['finish'], prepared['sessions'], Jsonb(row['snapshot'].get('pt_service_terms', PT_TERMS))))
        db.execute('INSERT INTO trainer_client_assignments(organization_id,trainer_relationship_id,client_id) VALUES(%s,%s,%s) ON CONFLICT(organization_id,trainer_relationship_id,client_id) WHERE ended_at IS NULL DO NOTHING', (org, prepared['trainer'], client))
        db.execute('UPDATE pt_purchase_states SET reserved_until=now(),resolution_reason=NULL WHERE organization_id=%s AND purchase_id=%s', (org, row['id']))
        repo.audit_pt(access, 'activated', {'starts_on': str(prepared['start']), 'ends_before': str(prepared['finish']), 'trainer': prepared['trainer']}, purchase=row['id'])

    def list(self, access):
        db, org = access.connection, access.organization_id
        is_trainer = 'trainer' in access.roles
        condition = '' if access.admin else (' AND e.trainer_relationship_id=%s AND NOT e.requires_reassignment AND e.revoked_at IS NULL' if is_trainer else ' AND e.member_relationship_id=%s')
        args = (org,) if access.admin else (org, access.context['id'])
        entitlements = db.execute("SELECT e.*,c.first_name,c.last_name, (e.requires_reassignment OR NOT EXISTS(SELECT 1 FROM organization_relationships r JOIN organization_staff_roles s ON s.organization_id=r.organization_id AND s.relationship_id=r.id WHERE r.organization_id=e.organization_id AND r.id=e.trainer_relationship_id AND r.status='active' AND s.revoked_at IS NULL AND s.role IN ('trainer','owner','admin'))) AS needs_reassignment FROM pt_entitlements e JOIN clients c ON c.organization_id=e.organization_id AND c.id=e.client_id WHERE e.organization_id=%s" + condition + ' ORDER BY e.ends_before DESC LIMIT 200', args).fetchall()
        # Trainers and members receive no payment references, prices or financial audit.
        condition = '' if access.admin else (' AND a.trainer_relationship_id=%s AND EXISTS(SELECT 1 FROM trainer_client_assignments assigned WHERE assigned.organization_id=a.organization_id AND assigned.trainer_relationship_id=a.trainer_relationship_id AND assigned.client_id=a.client_id AND assigned.ended_at IS NULL)' if is_trainer else ' AND c.organization_relationship_id=%s')
        appointments = db.execute('SELECT a.*,c.first_name,c.last_name FROM coaching_appointments a JOIN clients c ON c.organization_id=a.organization_id AND c.id=a.client_id WHERE a.organization_id=%s' + condition + ' ORDER BY a.starts_at DESC LIMIT 200', args).fetchall()
        trainers = db.execute("SELECT DISTINCT r.id,u.email FROM organization_relationships r JOIN users u ON u.id=r.user_id JOIN organization_staff_roles s ON s.organization_id=r.organization_id AND s.relationship_id=r.id WHERE r.organization_id=%s AND r.status='active' AND s.revoked_at IS NULL AND s.role IN ('trainer','owner','admin') ORDER BY r.id", (org,)).fetchall() if access.admin else []
        if not access.admin and access.context['organization_type'] == 'coaching':
            trainers = db.execute("SELECT DISTINCT r.id,COALESCE(NULLIF(trim(co.first_name || ' ' || co.last_name),''),'Assigned coach') AS name FROM organization_relationships r JOIN trainer_client_assignments a ON a.organization_id=r.organization_id AND a.trainer_relationship_id=r.id JOIN clients c ON c.organization_id=a.organization_id AND c.id=a.client_id LEFT JOIN coaches co ON co.user_id=r.user_id WHERE r.organization_id=%s AND r.status='active' AND a.ended_at IS NULL AND (%s OR c.organization_relationship_id=%s) AND (%s OR r.id=%s)", (org, is_trainer, access.context['id'], not is_trainer, access.context['id'])).fetchall()
        clients = [{'id': c['id'], 'first_name': c['first_name'], 'last_name': c['last_name']} for c in access.list_clients()] if access.context['organization_type'] == 'coaching' else []
        names = {t['id']: t.get('name', t.get('email', 'Assigned coach')) for t in trainers}
        if access.context['organization_type'] == 'gym':
            profile = self.repository.profile(db, org)
            for plan in (profile['configuration'].get('plans', []) if profile else []):
                if plan['kind'] == 'pt':
                    names[plan['trainer_relationship_id']] = plan['trainer_name']
        for row in entitlements + appointments:
            row['trainer_name'] = names.get(row['trainer_relationship_id'], 'Assigned coach')
        return {'entitlements': entitlements, 'appointments': appointments, 'trainers': trainers, 'clients': clients, 'admin': access.admin, 'can_complete': bool(access.roles), 'organization_type': access.context['organization_type'], 'terms': PT_TERMS}

    def reassign(self, access, purchase, trainer, consent, note):
        access.require_admin()
        if consent is not True or not note.strip():
            raise ValueError('Record member consent and the agreed reassignment reason.')
        repo, db, org = self.repository, access.connection, access.organization_id
        repo.lock_business(access)
        row = repo.lock(access, purchase, True)
        if not row or not any(p['kind'] == 'pt' for p in row['snapshot']['plans']):
            raise ResourceNotFound('PT purchase not found.')
        if row['status'] in {'cancelled', 'superseded', 'refunded', 'rejected'}:
            raise ValueError('This purchase cannot be reassigned.')
        if not repo.trainer_active(db, org, trainer):
            raise ValueError('Select active coaching staff in this business.')
        clients = repo.capacity_members(db, org, trainer, purchase)
        if row['relationship_id'] not in clients and len(clients) >= 10:
            raise ValueError('The replacement trainer has no capacity.')
        entitlement = db.execute('SELECT * FROM pt_entitlements WHERE organization_id=%s AND purchase_id=%s FOR UPDATE', (org, purchase)).fetchone()
        if entitlement:
            if entitlement['revoked_at'] or entitlement['ends_before'] <= today_india() or entitlement['remaining_sessions'] == 0:
                raise ValueError('Only usable PT entitlements can be reassigned.')
            old = entitlement['trainer_relationship_id']
            db.execute('UPDATE pt_entitlements SET trainer_relationship_id=%s,requires_reassignment=false WHERE organization_id=%s AND purchase_id=%s', (trainer, org, purchase))
            db.execute("UPDATE coaching_appointments SET status='cancelled',version=version+1 WHERE organization_id=%s AND entitlement_id=%s AND status='booked'", (org, purchase))
            db.execute('INSERT INTO trainer_client_assignments(organization_id,trainer_relationship_id,client_id) VALUES(%s,%s,%s) ON CONFLICT(organization_id,trainer_relationship_id,client_id) WHERE ended_at IS NULL DO NOTHING', (org, trainer, entitlement['client_id']))
            if old != trainer:
                db.execute('UPDATE trainer_client_assignments SET ended_at=now() WHERE organization_id=%s AND trainer_relationship_id=%s AND client_id=%s AND ended_at IS NULL AND NOT EXISTS(SELECT 1 FROM pt_entitlements WHERE organization_id=%s AND trainer_relationship_id=%s AND client_id=%s AND revoked_at IS NULL AND ends_before>%s AND (remaining_sessions IS NULL OR remaining_sessions>0))', (org, old, entitlement['client_id'], org, old, entitlement['client_id'], today_india()))
        else:
            repo.reserve(db, row, trainer)
        db.execute("UPDATE pt_purchase_states SET trainer_relationship_id=%s,reserved_until=now()+interval '24 hours',resolution_reason=NULL WHERE organization_id=%s AND purchase_id=%s", (trainer, org, purchase))
        repo.audit_pt(access, 'reassigned', {'trainer': trainer, 'member_consent': True, 'note': note, 'bookings_cancelled': bool(entitlement)}, purchase=purchase)
        repo.notice(db, org, row['relationship_id'], f'pt-reassigned:{purchase}:{uuid4()}', 'PT trainer reassigned', 'Your gym recorded your consent to a trainer reassignment. Existing bookings on this package were cancelled without consuming sessions; please book with the new trainer.')
        return {'reassigned': True}

    def require_entitlement(self, access, identifier):
        row = access.connection.execute('SELECT * FROM pt_entitlements WHERE organization_id=%s AND purchase_id=%s FOR UPDATE', (access.organization_id, identifier)).fetchone()
        if not row or not (access.admin or ('trainer' in access.roles and row['trainer_relationship_id'] == access.context['id'] and not row['requires_reassignment']) or (not access.roles and row['member_relationship_id'] == access.context['id'])):
            raise ResourceNotFound('PT entitlement not found.')
        return row

    def validate_booking(self, access, client, trainer, start, entitlement=None, excluding=None):
        db, org, repo = access.connection, access.organization_id, self.repository
        finish = start + timedelta(minutes=60)
        if not repo.trainer_active(db, org, trainer):
            raise ValueError('Trainer is unavailable. Ask the administrator for reassignment.')
        client_row = db.execute('SELECT c.*,r.status AS member_status FROM clients c LEFT JOIN organization_relationships r ON r.organization_id=c.organization_id AND r.id=c.organization_relationship_id WHERE c.organization_id=%s AND c.id=%s', (org, client)).fetchone()
        if not client_row or not client_row['is_active'] or client_row['member_status'] == 'inactive':
            raise ValueError('Client is inactive.')
        day, last_day = start.astimezone(INDIA).date(), (finish-timedelta(microseconds=1)).astimezone(INDIA).date()
        if entitlement:
            if entitlement['requires_reassignment']:
                raise ValueError('Trainer removal requires a consented reassignment before booking.')
            if entitlement['revoked_at'] or not entitlement['starts_on'] <= day <= last_day < entitlement['ends_before']:
                raise ValueError('Appointment must fit this PT entitlement period.')
            if coverage_end(repo.coverage(db, org, entitlement['member_relationship_id']), day) <= last_day:
                raise ValueError('Appointment needs paid gym membership coverage. Renew before booking or completing.')
            if entitlement['remaining_sessions'] is not None:
                booked = db.execute("SELECT count(*) AS n FROM coaching_appointments WHERE organization_id=%s AND entitlement_id=%s AND status='booked' AND (%s::uuid IS NULL OR id<>%s::uuid)", (org, entitlement['purchase_id'], excluding, excluding)).fetchone()['n']
                if entitlement['remaining_sessions'] <= booked:
                    raise ValueError('No unreserved session credit remains.')
            elif db.execute("SELECT 1 FROM coaching_appointments WHERE organization_id=%s AND client_id=%s AND status<>'cancelled' AND (starts_at AT TIME ZONE 'Asia/Kolkata')::date=%s AND (%s::uuid IS NULL OR id<>%s::uuid)", (org, client, day, excluding, excluding)).fetchone():
                raise ValueError('Duration PT allows one appointment per day.')
        if db.execute("SELECT 1 FROM coaching_appointments WHERE organization_id=%s AND (trainer_relationship_id=%s OR client_id=%s) AND status<>'cancelled' AND starts_at<%s AND ends_at>%s AND (%s::uuid IS NULL OR id<>%s::uuid)", (org, trainer, client, finish, start, excluding, excluding)).fetchone():
            raise ValueError('This time overlaps a trainer or client appointment.')
        return finish

    def book(self, access, payload):
        repo, db, org = self.repository, access.connection, access.organization_id
        repo.lock_business(access)
        start = appointment_time(payload['starts_at'])
        existing = db.execute('SELECT * FROM coaching_appointments WHERE organization_id=%s AND created_by=%s AND request_id=%s', (org, access.user_id, payload['request_id'])).fetchone()
        if existing:
            if str(existing['entitlement_id'] or '') != str(payload.get('entitlement_id') or '') or existing['starts_at'] != start or (not payload.get('entitlement_id') and (existing['client_id'] != payload.get('client_id') or existing['trainer_relationship_id'] != payload.get('trainer_relationship_id'))):
                raise ValueError('This request already created a different appointment.')
            return existing
        if start <= datetime.now(timezone.utc):
            raise ValueError('Book a future appointment.')
        entitlement = None
        if access.context['organization_type'] == 'gym':
            entitlement = self.require_entitlement(access, payload.get('entitlement_id'))
            client, trainer = entitlement['client_id'], entitlement['trainer_relationship_id']
        else:
            client, trainer = payload.get('client_id'), payload.get('trainer_relationship_id')
            access.require_client(client)
            assigned = db.execute('SELECT 1 FROM trainer_client_assignments WHERE organization_id=%s AND client_id=%s AND trainer_relationship_id=%s AND ended_at IS NULL', (org, client, trainer)).fetchone()
            if not assigned or ('trainer' in access.roles and not access.admin and trainer != access.context['id']):
                raise AccessDenied('Choose the assigned coach for this client.')
        finish = self.validate_booking(access, client, trainer, start, entitlement)
        identifier = uuid4()
        row = db.execute('INSERT INTO coaching_appointments(id,organization_id,request_id,created_by,entitlement_id,client_id,trainer_relationship_id,starts_at,ends_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *', (identifier, org, payload['request_id'], access.user_id, entitlement['purchase_id'] if entitlement else None, client, trainer, start, finish)).fetchone()
        repo.audit_pt(access, 'booked', {'starts_at': start.isoformat()}, appointment=identifier)
        return row

    def change_appointment(self, access, identifier, action, version, starts_at=None):
        if action not in {'cancel', 'complete', 'reschedule'}:
            raise ValueError('Unknown appointment action.')
        repo, db, org = self.repository, access.connection, access.organization_id
        repo.lock_business(access)
        row = db.execute('SELECT * FROM coaching_appointments WHERE organization_id=%s AND id=%s FOR UPDATE', (org, identifier)).fetchone()
        if not row:
            raise ResourceNotFound('Appointment not found.')
        entitlement = None
        if row['entitlement_id']:
            entitlement = self.require_entitlement(access, row['entitlement_id'])
            if row['trainer_relationship_id'] != entitlement['trainer_relationship_id'] and not access.admin:
                raise ResourceNotFound('Appointment no longer assigned to this trainer.')
        else:
            access.require_client(row['client_id'])
            if 'trainer' in access.roles and not access.admin and row['trainer_relationship_id'] != access.context['id']:
                raise ResourceNotFound('Appointment not found.')
        if action == 'complete' and not (access.admin or ('trainer' in access.roles and row['trainer_relationship_id'] == access.context['id'])):
            raise AccessDenied('Only authorized coaching staff can complete sessions.')
        target = {'cancel': 'cancelled', 'complete': 'completed', 'reschedule': 'booked'}[action]
        if row['status'] == target and action != 'reschedule':
            return row
        if row['status'] != 'booked' or version != row['version']:
            raise ValueError('Appointment changed. Refresh before continuing.')
        if action == 'complete':
            if row['ends_at'] > datetime.now(timezone.utc):
                raise ValueError('Complete the appointment after its scheduled end.')
            self.validate_booking(access, row['client_id'], row['trainer_relationship_id'], row['starts_at'], entitlement, identifier)
            if entitlement and entitlement['remaining_sessions'] is not None:
                db.execute('UPDATE pt_entitlements SET remaining_sessions=remaining_sessions-1 WHERE organization_id=%s AND purchase_id=%s', (org, entitlement['purchase_id']))
        start, finish = row['starts_at'], row['ends_at']
        if action == 'reschedule':
            start = appointment_time(starts_at)
            if start <= datetime.now(timezone.utc):
                raise ValueError('Reschedule to a future time.')
            finish = self.validate_booking(access, row['client_id'], row['trainer_relationship_id'], start, entitlement, identifier)
        result = db.execute('UPDATE coaching_appointments SET status=%s,starts_at=%s,ends_at=%s,version=version+1 WHERE organization_id=%s AND id=%s RETURNING *', (target, start, finish, org, identifier)).fetchone()
        repo.audit_pt(access, action, {'starts_at': start.isoformat(), 'previous_version': version}, appointment=identifier)
        return result
