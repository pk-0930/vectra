"""PT persistence with explicit organization keys and one mutation lock per business."""
from psycopg.types.json import Jsonb
from repositories.membership_repository import MembershipRepository


class PtRepository(MembershipRepository):
    def lock_business(self, access):
        if access.context['organization_type'] == 'gym':
            self.profile(access.connection, access.organization_id, lock=True)
        else:
            access.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f'appointments:{access.organization_id}',))

    def trainer_active(self, db, org, trainer):
        return db.execute("SELECT r.id FROM organization_relationships r JOIN organization_staff_roles s ON s.organization_id=r.organization_id AND s.relationship_id=r.id WHERE r.organization_id=%s AND r.id=%s AND r.status='active' AND s.revoked_at IS NULL AND s.role IN ('owner','admin','trainer') FOR SHARE OF r,s", (org, trainer)).fetchone() is not None

    def coverage(self, db, org, member):
        return db.execute('SELECT starts_on,ends_before FROM gym_membership_periods WHERE organization_id=%s AND relationship_id=%s AND revoked_at IS NULL ORDER BY starts_on', (org, member)).fetchall()

    def capacity_members(self, db, org, trainer, excluding=None):
        return {r['member'] for r in db.execute("SELECT e.member_relationship_id AS member FROM pt_entitlements e JOIN organization_relationships r ON r.organization_id=e.organization_id AND r.id=e.member_relationship_id WHERE e.organization_id=%s AND e.trainer_relationship_id=%s AND e.revoked_at IS NULL AND NOT e.requires_reassignment AND r.status='active' AND e.ends_before>(now() AT TIME ZONE 'Asia/Kolkata')::date AND (e.remaining_sessions IS NULL OR e.remaining_sessions>0) AND EXISTS(SELECT 1 FROM gym_membership_periods m WHERE m.organization_id=e.organization_id AND m.relationship_id=e.member_relationship_id AND m.revoked_at IS NULL AND m.starts_on<=GREATEST(e.starts_on,(now() AT TIME ZONE 'Asia/Kolkata')::date) AND m.ends_before>GREATEST(e.starts_on,(now() AT TIME ZONE 'Asia/Kolkata')::date)) UNION SELECT s.member_relationship_id FROM pt_purchase_states s JOIN gym_pending_purchases p ON p.id=s.purchase_id AND p.organization_id=s.organization_id WHERE s.organization_id=%s AND s.trainer_relationship_id=%s AND s.reserved_until>now() AND p.status IN ('pending','awaiting_verification') AND EXISTS(SELECT 1 FROM organization_relationships r WHERE r.organization_id=s.organization_id AND r.id=s.member_relationship_id AND r.status='active') AND (%s::uuid IS NULL OR s.purchase_id<>%s::uuid)", (org, trainer, org, trainer, excluding, excluding)).fetchall()}

    def audit_pt(self, access, action, details, purchase=None, appointment=None):
        access.connection.execute('INSERT INTO pt_audit(organization_id,actor_user_id,purchase_id,appointment_id,action,details) VALUES(%s,%s,%s,%s,%s,%s)', (access.organization_id, access.user_id, purchase, appointment, action, Jsonb(details)))

    def state(self, db, org, purchase):
        return db.execute('SELECT * FROM pt_purchase_states WHERE organization_id=%s AND purchase_id=%s', (org, purchase)).fetchone()

    def reserve(self, db, row, trainer):
        db.execute("INSERT INTO pt_purchase_states(purchase_id,organization_id,member_relationship_id,trainer_relationship_id,reserved_until) VALUES(%s,%s,%s,%s,now()+interval '24 hours') ON CONFLICT(purchase_id) DO NOTHING", (row['id'], row['organization_id'], row['relationship_id'], trainer))

    def ensure_client(self, access, row):
        db, org = access.connection, access.organization_id
        client = db.execute('SELECT id FROM clients WHERE organization_id=%s AND organization_relationship_id=%s', (org, row['relationship_id'])).fetchone()
        if client:
            return client['id']
        coach = access.staff_coach_id()
        return db.execute('INSERT INTO clients(coach_id,organization_id,organization_relationship_id,first_name,last_name,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,now(),now()) RETURNING id', (coach, org, row['relationship_id'], row['snapshot']['member_name'], '')).fetchone()['id']
