"""Gym setup persistence. All mutations share the profile lock and tenant boundary."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from repositories.identity_repository import IdentityRepository


class GymRepository(IdentityRepository):
    def profile(self, db, org, lock=False):
        return db.execute('SELECT * FROM gym_profiles WHERE organization_id=%s' +
                          (' FOR UPDATE' if lock else ''), (org,)).fetchone()

    def ensure_profile(self, db, org):
        db.execute('INSERT INTO gym_profiles(organization_id,public_id) VALUES(%s,%s) '
                   'ON CONFLICT(organization_id) DO NOTHING', (org, uuid4()))
        return self.profile(db, org, lock=True)

    def public_profile(self, db, public_id, lock=False):
        return db.execute('SELECT * FROM gym_profiles WHERE public_id=%s' +
                          (' FOR UPDATE' if lock else ''), (public_id,)).fetchone()

    def save_profile(self, db, org, actor, revision, config):
        db.execute('UPDATE gym_profiles SET configuration=%s,revision=%s,updated_at=now() '
                   'WHERE organization_id=%s', (Jsonb(config), revision, org))
        db.execute('INSERT INTO gym_setup_audit(organization_id,revision,actor_user_id,configuration) '
                   'VALUES(%s,%s,%s,%s)', (org, revision, actor, Jsonb(config)))

    def trainers(self, db, org):
        # Only identifiers and deliberately configured public names enter the public catalogue.
        rows = db.execute("SELECT r.id, u.email FROM organization_relationships r JOIN users u ON u.id=r.user_id "
                          "JOIN organization_staff_roles s ON s.relationship_id=r.id AND s.organization_id=r.organization_id "
                          "WHERE r.organization_id=%s AND r.status='active' AND s.role IN ('trainer','owner','admin') "
                          "AND s.revoked_at IS NULL ORDER BY r.id FOR SHARE OF r,s", (org,)).fetchall()
        return list({row['id']: row for row in rows}.values())

    def purchases(self, db, org, user):
        return db.execute('SELECT p.* FROM gym_pending_purchases p JOIN organization_relationships r '
                          'ON r.id=p.relationship_id AND r.organization_id=p.organization_id '
                          "WHERE p.organization_id=%s AND r.user_id=%s AND r.status='active' "
                          'ORDER BY p.created_at DESC LIMIT 100', (org, user)).fetchall()

    def audit(self, db, org):
        return db.execute('SELECT revision,actor_user_id,created_at FROM gym_setup_audit '
                          'WHERE organization_id=%s ORDER BY revision DESC LIMIT 25', (org,)).fetchall()

    def asset_matches(self, db, identifier, org, kind):
        return db.execute('SELECT id FROM gym_assets WHERE id=%s AND organization_id=%s AND kind=%s',
                          (identifier, org, kind)).fetchone() is not None

    def recent_upload_count(self, db, org):
        return db.execute("SELECT count(*) AS n FROM gym_assets WHERE organization_id=%s AND created_at>now()-interval '1 hour'",
                          (org,)).fetchone()['n']

    def insert_asset(self, db, identifier, org, kind, png, actor):
        db.execute('INSERT INTO gym_assets(id,organization_id,kind,png,created_by) VALUES(%s,%s,%s,%s,%s)',
                   (identifier, org, kind, png, actor))

    def asset(self, db, identifier):
        return db.execute('SELECT * FROM gym_assets WHERE id=%s', (identifier,)).fetchone()

    def asset_published(self, db, identifier, org):
        return db.execute('SELECT 1 FROM gym_setup_audit WHERE organization_id=%s AND '
                          "(configuration->>'logo_id'=%s OR configuration->'payment'->>'qr_asset_id'=%s) LIMIT 1",
                          (org, str(identifier), str(identifier))).fetchone() is not None

    def organization(self, db, org):
        return db.execute('SELECT * FROM organizations WHERE id=%s FOR SHARE', (org,)).fetchone()

    def purchase_request(self, db, org, relationship, request_id):
        return db.execute('SELECT * FROM gym_pending_purchases WHERE organization_id=%s AND relationship_id=%s AND request_id=%s',
                          (org, relationship, request_id)).fetchone()

    def lock_purchase(self, db, identifier, org, relationship):
        return db.execute('SELECT * FROM gym_pending_purchases WHERE id=%s AND organization_id=%s AND relationship_id=%s FOR UPDATE',
                          (identifier, org, relationship)).fetchone()

    def supersede(self, db, identifier):
        db.execute("UPDATE gym_pending_purchases SET status='superseded' WHERE id=%s", (identifier,))

    def insert_purchase(self, db, org, relationship, request_id, digest, revision, snapshot, total, replaces):
        return db.execute('INSERT INTO gym_pending_purchases(id,organization_id,relationship_id,request_id,request_hash,profile_revision,snapshot,amount_paise,replaces_id) '
                          'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',
                          (uuid4(), org, relationship, request_id, digest, revision, Jsonb(snapshot), total, replaces)).fetchone()

    def admin_purchases(self, db, org):
        return db.execute('SELECT id,snapshot,amount_paise,currency,status,created_at FROM gym_pending_purchases '
                          'WHERE organization_id=%s ORDER BY created_at DESC LIMIT 100', (org,)).fetchall()
