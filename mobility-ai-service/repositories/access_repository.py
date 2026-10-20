"""Request-bound access adapter for the existing coaching service contracts.

The caller holds a transaction for the request. Relationship, role and assignment
locks make revocation serialize with in-flight operations. No selected business
or coach ID from a browser is an authorization grant.
"""
from contextlib import contextmanager

from repositories.organization_repository import OrganizationRepository


class AccessDenied(Exception):
    pass


class ResourceNotFound(Exception):
    pass


class AccessRepository(OrganizationRepository):
    def __init__(self, connection, organization_id, user_id, member_mode=False):
        super().__init__(None, organization_id)
        self.connection = connection
        self.user_id = user_id
        self.context = connection.execute(
            "SELECT r.id, o.organization_type FROM organization_relationships r "
            "JOIN organizations o ON o.id=r.organization_id "
            "WHERE r.organization_id=%s AND r.user_id=%s "
            "AND r.status='active' AND o.status='active' FOR SHARE OF r,o",
            (organization_id, user_id),
        ).fetchone()
        if self.context is None:
            raise AccessDenied('Business access is unavailable.')
        rows = connection.execute(
            "SELECT role FROM organization_staff_roles WHERE organization_id=%s "
            "AND relationship_id=%s AND revoked_at IS NULL FOR SHARE",
            (organization_id, self.context['id']),
        ).fetchall()
        self.roles = set() if member_mode else {r['role'] for r in rows}
        assignments = connection.execute(
            "SELECT client_id FROM trainer_client_assignments WHERE organization_id=%s "
            "AND trainer_relationship_id=%s AND ended_at IS NULL FOR SHARE",
            (organization_id, self.context['id']),
        ).fetchall()
        self.assigned = {r['client_id'] for r in assignments}
        self.admin = bool(self.roles & {'owner', 'admin'})

    @contextmanager
    def _connect(self):
        yield self.connection

    def require_staff(self):
        if not self.roles:
            raise AccessDenied('Coaching staff access is required.')

    def require_admin(self):
        if not self.admin:
            raise AccessDenied('Business administrator access is required.')

    def can_read(self, client):
        return bool(client and (self.admin or
            ('trainer' in self.roles and client['id'] in self.assigned) or
            (not self.roles and client.get('organization_relationship_id') == self.context['id'])))

    def require_client(self, client_id, staff=False):
        client = super().fetch_client(client_id)
        if not self.can_read(client):
            raise ResourceNotFound('Client not found.')
        if staff and not (self.admin or ('trainer' in self.roles and client_id in self.assigned)):
            raise AccessDenied('Assigned coaching staff access is required.')
        return client

    def staff_coach_id(self):
        self.require_staff()
        # Profile creation does not create another organization (V6).
        row = self.connection.execute(
            "INSERT INTO coaches(user_id, first_name, last_name, created_at, updated_at) "
            "VALUES(%s,'Staff','',now(),now()) ON CONFLICT(user_id) DO UPDATE "
            "SET user_id=EXCLUDED.user_id RETURNING id", (self.user_id,),
        ).fetchone()
        return row['id']

    def list_clients(self, coach_id=None):
        return [self.decorate_client(c) for c in super().list_clients() if self.can_read(c)]

    def decorate_client(self, client):
        goals = super().list_records('client_goals', client_id=client['id'])
        current = next((g for g in reversed(goals) if g['is_current']), {})
        return {**client, 'current_goal_type': current.get('goal_type'),
                'current_goal_notes': current.get('notes') if (self.admin or ('trainer' in self.roles and client['id'] in self.assigned)) else None}

    def fetch_client(self, client_id, coach_id=None):
        return self.decorate_client(self.require_client(client_id))

    def create_client(self, payload):
        self.require_admin()
        payload = dict(payload)
        payload.pop('coach_id', None)
        return super().create_client(coach_id=self.staff_coach_id(), payload=payload)

    def update_client(self, client_id, coach_id, payload):
        self.require_client(client_id, staff=True)
        return super().update_client(client_id, payload)

    def record(self, table, record_id, staff=False):
        row = super().fetch_record(table, record_id)
        if row is None:
            raise ResourceNotFound('Record not found.')
        self.require_client(row['client_id'], staff=staff)
        return row

    def insert(self, table, payload, staff=False):
        payload = dict(payload)
        client_id = payload.pop('client_id')
        self.require_client(client_id, staff=staff)
        return super().create_record(table, client_id=client_id, payload=payload)

    def add_client_goal(self, payload):
        return self.insert('client_goals', payload, staff=True)

    def add_progress_photo(self, payload):
        self.require_coaching_upload(payload['client_id'])
        return self.insert('client_progress_photos', payload)

    def coaching_access(self, client_id):
        client = self.require_client(client_id)
        if self.roles or self.context['organization_type'] == 'coaching':
            return {'can_upload': bool(client['is_active']), 'historical_access': True}
        row = self.connection.execute(
            "SELECT 1 FROM pt_entitlements p JOIN gym_membership_periods m "
            "ON m.organization_id=p.organization_id AND m.relationship_id=p.member_relationship_id "
            "WHERE p.organization_id=%s AND p.client_id=%s AND p.revoked_at IS NULL AND NOT p.requires_reassignment "
            "AND p.starts_on<=(now() AT TIME ZONE 'Asia/Kolkata')::date "
            "AND p.ends_before>(now() AT TIME ZONE 'Asia/Kolkata')::date "
            "AND (p.remaining_sessions IS NULL OR p.remaining_sessions>0) "
            "AND m.revoked_at IS NULL AND m.starts_on<=(now() AT TIME ZONE 'Asia/Kolkata')::date "
            "AND m.ends_before>(now() AT TIME ZONE 'Asia/Kolkata')::date "
            "AND EXISTS(SELECT 1 FROM organization_staff_roles s JOIN organization_relationships r "
            "ON r.organization_id=s.organization_id AND r.id=s.relationship_id "
            "WHERE s.organization_id=p.organization_id AND s.relationship_id=p.trainer_relationship_id "
            "AND s.revoked_at IS NULL AND r.status='active') LIMIT 1 FOR SHARE OF p,m",
            (self.organization_id, client_id),
        ).fetchone()
        return {'can_upload': bool(row and client['is_active']), 'historical_access': True}

    def require_coaching_upload(self, client_id):
        if not self.coaching_access(client_id)['can_upload']:
            raise AccessDenied('New uploads require an active coaching profile and, for gym members, current paid membership and PT coverage. Your published history remains available.')

    def list_goals(self, client_id):
        self.require_client(client_id)
        rows = list(reversed(super().list_records('client_goals', client_id=client_id)))
        # Existing notes are private coach material, not member-published text.
        return rows if self.roles else [{**row, 'notes': None} for row in rows]

    def list_progress_photos(self, client_id):
        self.require_client(client_id)
        return list(reversed(super().list_records('client_progress_photos', client_id=client_id)))

    def resolve_photo(self, blob_name):
        row = super().resolve_photo(blob_name)
        if row is None:
            raise ResourceNotFound('Photo not found.')
        self.require_client(row['client_id'])
        return row

    def create_plan(self, table, payload):
        row = self.insert(table, {**payload, 'created_by_coach_id': self.staff_coach_id()}, staff=True)
        client = self.require_client(payload['client_id'], staff=True)
        if client.get('organization_relationship_id'):
            self.connection.execute(
                'INSERT INTO notification_inbox(organization_id,relationship_id,event_key,subject,message) '
                'VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (self.organization_id, client['organization_relationship_id'], f'plan:{table}:{row["id"]}',
                 'Your coaching plan is ready', 'A new published plan is available in your member workspace.'),
            )
        return row

    def list_plans(self, table, client_id, coach_id=None):
        self.require_client(client_id)
        return list(reversed(super().list_records(table, client_id=client_id)))

    def fetch_plan(self, table, plan_id, coach_id=None):
        return self.record(table, plan_id)

    def create_plan_draft(self, payload):
        return self.insert('ai_plan_drafts', {**payload, 'coach_id': self.staff_coach_id()}, staff=True)

    def fetch_plan_draft(self, draft_id, coach_id=None):
        row = self.record('ai_plan_drafts', draft_id, staff=True)
        # Serialize concurrent approval/edit requests before service status checks.
        self.connection.execute('SELECT id FROM ai_plan_drafts WHERE id=%s AND organization_id=%s FOR UPDATE',
                                (draft_id, self.organization_id))
        return self.record('ai_plan_drafts', draft_id, staff=True)

    def list_plan_drafts(self, client_id, coach_id=None, plan_kind=None):
        self.require_client(client_id, staff=True)
        return [r for r in reversed(super().list_records('ai_plan_drafts', client_id=client_id))
                if plan_kind is None or r['plan_kind'] == plan_kind]

    def update_plan_draft(self, draft_id, coach_id, payload):
        row = self.fetch_plan_draft(draft_id)
        if row['status'] != 'draft':
            raise AccessDenied('Only draft plans can be changed.')
        return super().update_record('ai_plan_drafts', draft_id, payload)

    regenerate_plan_draft = update_plan_draft

    def set_plan_draft_status(self, draft_id, coach_id, status, updated_at, approved_plan_id):
        return self.update_plan_draft(draft_id, coach_id, dict(
            status=status, updated_at=updated_at, approved_plan_id=approved_plan_id))

    def insert_form_analysis(self, payload):
        self.require_coaching_upload(payload['client_id'])
        return self.insert('form_analyses', payload)

    def fetch_form_analysis(self, analysis_id):
        return self.record('form_analyses', analysis_id)

    def fetch_form_analysis_for_coach(self, analysis_id, coach_id=None):
        return self.fetch_form_analysis(analysis_id)

    def fetch_form_analyses(self, coach_id, limit, client_id=None):
        clients = [self.require_client(client_id)] if client_id is not None else self.list_clients()
        rows = [r for c in clients for r in super(AccessRepository, self).list_records(
            'form_analyses', client_id=c['id'])]
        return sorted(rows, key=lambda r: r['created_at'], reverse=True)[:max(0, min(limit, 100))]

    def update_form_analysis_feedback(self, analysis_id, note, updated_at):
        self.record('form_analyses', analysis_id, staff=True)
        return super().update_record('form_analyses', analysis_id, {
            'coach_feedback_note': note, 'updated_at': updated_at})

    def resolve_frame(self, filename):
        row = self.connection.execute(
            'SELECT analysis_id FROM form_analysis_assets WHERE organization_id=%s AND blob_name=%s',
            (self.organization_id, filename),
        ).fetchone()
        if row is None:
            raise ResourceNotFound('Frame not found.')
        return self.record('form_analyses', row['analysis_id'])

    def list_people(self):
        self.require_admin()
        return self.connection.execute(
            "SELECT r.id, u.email, r.status, ARRAY(SELECT role FROM organization_staff_roles s "
            "WHERE s.organization_id=r.organization_id AND s.relationship_id=r.id "
            "AND s.revoked_at IS NULL ORDER BY role) AS roles "
            "FROM organization_relationships r JOIN users u ON u.id=r.user_id "
            "WHERE r.organization_id=%s ORDER BY r.id", (self.organization_id,),
        ).fetchall()

    def revoke_role(self, relationship_id, role):
        self.require_admin()
        if role not in {'admin', 'trainer'} or (role == 'admin' and 'owner' not in self.roles):
            raise AccessDenied('Only owners can remove admins; ownership cannot be removed here.')
        self.connection.execute(
            'UPDATE organization_staff_roles SET revoked_at=now() WHERE organization_id=%s '
            'AND relationship_id=%s AND role=%s AND revoked_at IS NULL',
            (self.organization_id, relationship_id, role),
        )

    def assign_trainer(self, client_id, relationship_id, active):
        self.require_admin()
        self.require_client(client_id)
        trainer = self.connection.execute(
            "SELECT r.id FROM organization_relationships r WHERE r.organization_id=%s "
            "AND r.id=%s AND r.status='active' AND EXISTS(SELECT 1 FROM organization_staff_roles s "
            "WHERE s.organization_id=r.organization_id AND s.relationship_id=r.id "
            "AND s.revoked_at IS NULL AND s.role IN ('trainer','owner','admin')) FOR SHARE",
            (self.organization_id, relationship_id),
        ).fetchone()
        if trainer is None:
            raise ResourceNotFound('Active staff relationship not found.')
        if active:
            self.connection.execute(
                'INSERT INTO trainer_client_assignments(organization_id,trainer_relationship_id,client_id) '
                'VALUES(%s,%s,%s) ON CONFLICT (organization_id,trainer_relationship_id,client_id) '
                'WHERE ended_at IS NULL DO NOTHING', (self.organization_id, relationship_id, client_id),
            )
        else:
            self.connection.execute(
                'UPDATE trainer_client_assignments SET ended_at=now() WHERE organization_id=%s '
                'AND trainer_relationship_id=%s AND client_id=%s AND ended_at IS NULL',
                (self.organization_id, relationship_id, client_id),
            )
