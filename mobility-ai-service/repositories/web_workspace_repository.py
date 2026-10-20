"""Web inbox, reports and rollout storage within the authorized request transaction."""
from config.features import analysis_enabled
from repositories.access_repository import ResourceNotFound


class WebWorkspaceRepository:
    def ready(self, platform_repository):
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(**platform_repository.config.connection_kwargs(),
                             connect_timeout=3, row_factory=dict_row) as db:
            db.execute("SET LOCAL statement_timeout='3s'")
            return db.execute(
                "SELECT EXISTS(SELECT 1 FROM flyway_schema_history WHERE version='13' AND success) AS ready"
            ).fetchone()['ready']

    def inbox(self, access, before=None, limit=30):
        rows = access.connection.execute(
            'SELECT id,subject,message,created_at,read_at FROM notification_inbox '
            'WHERE organization_id=%s AND relationship_id=%s AND (%s::bigint IS NULL OR id<%s) '
            "AND (%s OR event_key NOT LIKE 'analysis:%%') ORDER BY id DESC LIMIT %s",
            (access.organization_id, access.context['id'], before, before, analysis_enabled(), limit + 1),
        ).fetchall()
        unread = access.connection.execute(
            'SELECT count(*) AS n FROM notification_inbox WHERE organization_id=%s '
            "AND relationship_id=%s AND read_at IS NULL AND (%s OR event_key NOT LIKE 'analysis:%%')",
            (access.organization_id, access.context['id'], analysis_enabled()),
        ).fetchone()['n']
        return {'items': rows[:limit], 'unread': unread,
                'next_before': rows[limit - 1]['id'] if len(rows) > limit else None}

    def mark_read(self, access, identifier):
        row = access.connection.execute(
            'UPDATE notification_inbox SET read_at=COALESCE(read_at,now()) '
            'WHERE organization_id=%s AND relationship_id=%s AND id=%s RETURNING id,read_at',
            (access.organization_id, access.context['id'], identifier),
        ).fetchone()
        if not row:
            raise ResourceNotFound('Inbox item not found.')
        return row

    def announce(self, access, identifier, audience, subject, message):
        db, org = access.connection, access.organization_id
        # Serializes retries without issuing a second audience snapshot.
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                   (f'announcement:{org}:{identifier}',))
        previous = db.execute('SELECT * FROM business_announcements WHERE organization_id=%s AND id=%s',
                              (org, identifier)).fetchone()
        if previous:
            if any(previous[k] != v for k, v in {'sender_user_id': access.user_id, 'audience': audience,
                                                'subject': subject, 'message': message}.items()):
                raise ValueError('This announcement request was already used with different content.')
            return {'id': identifier, 'recipient_count': previous['recipient_count']}
        # Membership is represented by a gym purchase, separate from coaching/staff roles.
        audiences = {
            'all': 'true',
            'trainers': "EXISTS(SELECT 1 FROM organization_staff_roles s WHERE s.organization_id=r.organization_id AND s.relationship_id=r.id AND s.role='trainer' AND s.revoked_at IS NULL)",
            'members': 'EXISTS(SELECT 1 FROM gym_pending_purchases p WHERE p.organization_id=r.organization_id AND p.relationship_id=r.id)',
            'clients': 'EXISTS(SELECT 1 FROM clients c WHERE c.organization_id=r.organization_id AND c.organization_relationship_id=r.id AND c.is_active)',
        }
        rows = db.execute(
            'SELECT r.id FROM organization_relationships r WHERE r.organization_id=%s '
            "AND r.status='active' AND " + audiences[audience] + ' FOR SHARE OF r', (org,),
        ).fetchall()
        db.execute('INSERT INTO business_announcements(id,organization_id,sender_user_id,audience,subject,message,recipient_count) '
                   'VALUES(%s,%s,%s,%s,%s,%s,%s)',
                   (identifier, org, access.user_id, audience, subject, message, len(rows)))
        for row in rows:
            db.execute('INSERT INTO notification_inbox(organization_id,relationship_id,event_key,subject,message) '
                       'VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                       (org, row['id'], f'announcement:{identifier}', subject, message))
        return {'id': identifier, 'recipient_count': len(rows)}

    def reports(self, access, start, end, today):
        db, org = access.connection, access.organization_id
        collections = db.execute(
            'SELECT method,count(*) AS payments,COALESCE(sum(amount_paise),0)::bigint AS amount_paise '
            'FROM gym_verified_payments WHERE organization_id=%s AND received_on BETWEEN %s AND %s GROUP BY method',
            (org, start, end),
        ).fetchall()
        # Refund date is the recorded event date in India. Include refunds of unconfirmed
        # receipts separately so they cannot silently distort the verified-payment ledger.
        refunds = db.execute(
            "SELECT (v.purchase_id IS NOT NULL) AS verified_collection,count(*) AS refunds,"
            "COALESCE(sum((e.details->>'amount_paise')::bigint),0)::bigint AS amount_paise "
            'FROM gym_payment_events e LEFT JOIN gym_verified_payments v ON v.organization_id=e.organization_id AND v.purchase_id=e.purchase_id '
            "WHERE e.organization_id=%s AND e.kind='refunded' AND "
            "(e.created_at AT TIME ZONE 'Asia/Kolkata')::date BETWEEN %s AND %s GROUP BY (v.purchase_id IS NOT NULL)",
            (org, start, end),
        ).fetchall()
        membership = db.execute(
            'SELECT count(DISTINCT m.relationship_id) AS active_members, '
            'count(DISTINCT m.relationship_id) FILTER(WHERE m.ends_before<=%s::date+7 AND NOT EXISTS('
            'SELECT 1 FROM gym_membership_periods n WHERE n.organization_id=m.organization_id AND n.relationship_id=m.relationship_id '
            'AND n.revoked_at IS NULL AND n.starts_on<=m.ends_before AND n.ends_before>m.ends_before)) AS expiring_members '
            'FROM gym_membership_periods m JOIN organization_relationships r ON r.organization_id=m.organization_id AND r.id=m.relationship_id '
            "WHERE m.organization_id=%s AND r.status='active' AND m.revoked_at IS NULL AND m.starts_on<=%s AND m.ends_before>%s",
            (today, org, today, today),
        ).fetchone()
        pt = db.execute(
            "SELECT p.status,count(*) AS purchases,COALESCE(sum((plan->>'amount_paise')::bigint),0)::bigint AS amount_paise "
            "FROM gym_pending_purchases p CROSS JOIN LATERAL jsonb_array_elements(p.snapshot->'plans') plan "
            "WHERE p.organization_id=%s AND plan->>'kind'='pt' AND "
            "(p.created_at AT TIME ZONE 'Asia/Kolkata')::date BETWEEN %s AND %s GROUP BY p.status", (org, start, end),
        ).fetchall()
        return {'start': start, 'end': end, 'as_of': today, 'collections': collections, 'refunds': refunds,
                'memberships': membership, 'pt_purchases': pt,
                'purchases_enabled': self.rollout(access)['purchases_enabled']}

    def rollout(self, access):
        row = access.connection.execute('SELECT purchases_enabled FROM business_web_rollout WHERE organization_id=%s',
                                        (access.organization_id,)).fetchone()
        return row or {'purchases_enabled': True}

    def set_rollout(self, access, enabled):
        # Match gym purchase locking order; toggling does not revoke paid entitlements.
        access.connection.execute('SELECT organization_id FROM gym_profiles WHERE organization_id=%s FOR UPDATE',
                                  (access.organization_id,))
        access.connection.execute('INSERT INTO business_web_rollout(organization_id,purchases_enabled,updated_by) VALUES(%s,%s,%s) '
                                  'ON CONFLICT(organization_id) DO UPDATE SET purchases_enabled=EXCLUDED.purchases_enabled,updated_by=EXCLUDED.updated_by,updated_at=now()',
                                  (access.organization_id, enabled, access.user_id))
        access.connection.execute('INSERT INTO business_web_rollout_audit(organization_id,actor_user_id,purchases_enabled) VALUES(%s,%s,%s)',
                                  (access.organization_id, access.user_id, enabled))
        return {'purchases_enabled': enabled}
