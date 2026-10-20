"""Step 2 permissions exercised on real PostgreSQL, not mock SQL."""
from contextlib import contextmanager
from datetime import UTC, datetime
import json
import sys
import unittest
import uuid

import test_organization_foundations as foundations
sys.path.insert(0, str(foundations.ROOT / 'mobility-ai-service'))
from psycopg.rows import dict_row
from config.postgres_config import PostgresConfig
from repositories.access_repository import AccessRepository, AccessDenied, ResourceNotFound
from repositories.platform_repository import PostgresPlatformRepository
from repositories.worker_repository import WorkerRepository
from services.client_service import ClientService
from services.plan_service import PlanService
from services.job_service import JobService
from services.queue_job_processor import process_queue_message, NonRetryableQueueMessageError
from unittest.mock import Mock


@unittest.skipUnless(foundations.ENABLED, 'Set VECTRA_RUN_MIGRATION_TESTS=1')
class AccessControlTests(foundations.DisposablePostgresTests):
    def setUp(self):
        self.db = 'access_' + uuid.uuid4().hex[:10]
        self.create_database(self.db)
        self.flyway(self.db, 'migrate', '-target=4')
        with self.connect(self.db) as c:
            c.execute((foundations.ROOT / 'database/tests/legacy_fixture.sql').read_text())
        self.flyway(self.db, 'migrate')
        self.config = PostgresConfig(host='127.0.0.1', port=self.port, dbname=self.db,
                                     user='postgres', password=self.password, sslmode='disable')
        with self.connect(self.db) as c:
            self.org = c.execute('SELECT organization_id FROM clients WHERE id=101').fetchone()[0]
            self.other = c.execute('SELECT organization_id FROM clients WHERE id=102').fetchone()[0]
            c.execute("INSERT INTO users(id,email,password_hash,created_at,updated_at) VALUES(201,'staff@test.invalid','fixture',now(),now()),(202,'member@test.invalid','fixture',now(),now()),(203,'admin@test.invalid','fixture',now(),now())")
            self.staff = c.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,201) RETURNING id',(self.org,)).fetchone()[0]
            self.member = c.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,202) RETURNING id',(self.org,)).fetchone()[0]
            self.admin = c.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,203) RETURNING id',(self.org,)).fetchone()[0]
            c.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'trainer'),(%s,%s,'admin')",(self.org,self.staff,self.org,self.admin))
            c.execute('UPDATE clients SET organization_relationship_id=%s WHERE id=101',(self.member,))
            c.execute("INSERT INTO clients(id,coach_id,organization_id,organization_relationship_id,first_name,last_name,created_at,updated_at) VALUES(103,101,%s,%s,'Staff','Member',now(),now())",(self.org,self.staff))
            c.execute("SELECT setval(pg_get_serial_sequence('clients','id'),103)")
            c.execute('INSERT INTO trainer_client_assignments(organization_id,trainer_relationship_id,client_id) VALUES(%s,%s,101)',(self.org,self.staff))
        with self.connect(self.db) as c:
            # Step 2 authorization fixtures represent accounts that already proved email ownership.
            c.execute('UPDATE users SET email_verified_at=now(),verification_required=false')
        self.now = datetime.now(UTC)

    @contextmanager
    def access(self, user, org=None):
        with self.connect(self.db, row_factory=dict_row) as c:
            yield AccessRepository(c, org or self.org, user)

    def test_owner_admin_trainer_member_and_cross_business_matrix(self):
        for user, expected in [(101,[101,103]),(203,[101,103]),(201,[101]),(202,[101])]:
            with self.subTest(user=user), self.access(user) as repo:
                self.assertEqual([r['id'] for r in repo.list_clients()],expected)
                with self.assertRaises(ResourceNotFound): repo.fetch_client(102)
                self.assertEqual(repo.fetch_plan('nutrition_plans',1)['client_id'],101)
        with self.assertRaises(AccessDenied), self.access(201,self.other): pass
        with self.access(202) as repo:
            with self.assertRaises(AccessDenied): repo.fetch_plan_draft(1)
            with self.assertRaises(AccessDenied): repo.update_client(101,None,{'first_name':'forged'})
            with self.assertRaises(AccessDenied): repo.list_people()
            with self.assertRaises(AccessDenied): repo.update_form_analysis_feedback('owned-analysis','forged',self.now)
        with self.access(201) as repo:
            with self.assertRaises(AccessDenied): repo.create_client({})
            with self.assertRaises(AccessDenied): repo.list_people()
            with self.assertRaises(ResourceNotFound): repo.require_client(103,staff=True)

    def test_revocation_removes_trainer_access_but_preserves_member(self):
        with self.access(101) as owner: owner.revoke_role(self.staff,'trainer')
        with self.access(201) as repo:
            self.assertEqual([r['id'] for r in repo.list_clients()],[103])
            with self.assertRaises(ResourceNotFound): repo.fetch_client(101)
            with self.assertRaises(ResourceNotFound): repo.fetch_form_analysis('owned-analysis')
        with self.access(101) as owner:
            with self.assertRaises(AccessDenied): owner.revoke_role(owner.context['id'],'owner')

    def test_assignment_end_and_inactive_business_revoke_access(self):
        with self.access(101) as owner: owner.assign_trainer(101,self.staff,False)
        with self.access(201) as repo:
            with self.assertRaises(ResourceNotFound): repo.fetch_client(101)
        with self.connect(self.db) as c: c.execute("UPDATE organizations SET status='inactive' WHERE id=%s",(self.org,))
        with self.assertRaises(AccessDenied), self.access(101): pass

    def test_staff_profile_and_business_coaching_services_do_not_create_business(self):
        with self.access(203) as repo:
            profile = repo.staff_coach_id()
            result = PlanService(repo).create_plan('nutrition',profile,101,dict(period_type='weekly',period_start='2026-10-17',period_end='2026-10-23',title='Admin plan',content={'meals':[]}))
            self.assertEqual(result['created_by_coach_id'], profile)
            created = ClientService(repo).create_client(profile,dict(first_name='Admin',last_name='Client'))
            self.assertEqual(created['coach_id'],profile)
        with self.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM organizations').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT count(*) FROM legacy_coach_organizations WHERE coach_id=%s',(profile,)).fetchone()[0],0)
        import secrets
        from config.auth_config import AuthConfig
        from services.auth_service import AuthService
        from services.security_service import SecurityService
        auth = AuthService(PostgresPlatformRepository(self.config),
                           SecurityService(AuthConfig(secrets.token_urlsafe(32), 24)))
        registered = auth.sign_up_coach(email='new-coach@example.invalid', password='fixture-password',
                                        first_name='New', last_name='Coach')
        self.assertEqual(len(registered['organizations']), 1)
        self.assertEqual(registered['organizations'][0]['staff_roles'], ['owner'])
        self.assertEqual(registered['organizations'][0]['organization_type'], 'coaching')
        with self.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM organizations').fetchone()[0], 3)
            self.assertEqual(c.execute('SELECT billing_transition FROM organizations WHERE id=%s',
                             (registered['organizations'][0]['organization_id'],)).fetchone()[0], 'none')

    def test_worker_scope_retry_poison_completion_and_media_ownership(self):
        a=JobService(WorkerRepository(self.config,self.org))
        b=JobService(WorkerRepository(self.config,self.other))
        with self.connect(self.db) as c: c.execute("UPDATE form_analyses SET status='queued' WHERE id='owned-analysis'")
        self.assertIsNone(b.mark_job_running('owned-analysis'))
        self.assertIsNone(b.mark_job_failed('owned-analysis','forged'))
        self.assertIsNone(b.requeue_job_for_retry('owned-analysis','forged'))
        self.assertIsNotNone(a.mark_job_running('owned-analysis'))
        self.assertIsNotNone(a.requeue_job_for_retry('owned-analysis','temporary'))
        self.assertIsNotNone(a.mark_job_running('owned-analysis'))
        self.assertIsNotNone(a.mark_job_completed('owned-analysis',{'frames':[{'image_path':'/frames/owned-analysis/frame.jpg'}]}))
        self.assertIsNone(a.mark_job_failed('owned-analysis','late poison'))
        with self.access(202) as repo:
            self.assertEqual(repo.resolve_frame('owned-analysis/frame.jpg')['id'],'owned-analysis')
        with self.access(102,self.other) as repo:
            with self.assertRaises(ResourceNotFound): repo.resolve_frame('owned-analysis/frame.jpg')
        root=JobService(PostgresPlatformRepository(self.config))
        runner=Mock()
        with self.assertRaises(NonRetryableQueueMessageError): process_queue_message(root,runner,{'job_id':'owned-analysis','analysis_type':'squat'})
        with self.assertRaises(NonRetryableQueueMessageError): process_queue_message(root,runner,{'organization_id':self.other,'job_id':'owned-analysis','analysis_type':'squat'})
        runner.run_squat_job.assert_not_called()

    def test_photo_and_draft_resources_are_authorized_before_access(self):
        with self.access(202) as repo:
            photos=repo.list_progress_photos(101)
            self.assertEqual(repo.resolve_photo(photos[0]['blob_name'])['client_id'],101)
            with self.assertRaises(AccessDenied): repo.list_plan_drafts(101)
        with self.access(102,self.other) as repo:
            with self.assertRaises(ResourceNotFound): repo.resolve_photo(photos[0]['blob_name'])
            with self.assertRaises(ResourceNotFound): repo.fetch_plan_draft(1)
        with self.access(201) as repo:
            self.assertEqual(repo.fetch_plan_draft(1)['client_id'],101)
        self.flyway(self.db,'validate')

    def test_http_routes_bind_real_access_and_protect_media_and_mutations(self):
        import asyncio
        from contextlib import ExitStack
        import importlib.util
        from pathlib import Path
        import secrets
        from unittest.mock import patch
        from config.features import analysis_enabled
        from config.auth_config import AuthConfig
        from services.security_service import SecurityService
        from services.auth_service import AuthService
        from services.ai_plan_draft_service import AiPlanDraftService
        # Load app without reading local settings, contacting storage or constructing pose models.
        with ExitStack() as stack:
            stack.enter_context(patch('config.local_settings_loader.load_local_settings'))
            for mod, name in [('auth_service','AuthService'),('client_service','ClientService'),
                              ('plan_service','PlanService'),('job_service','JobService'),
                              ('job_runner','JobRunner'),('blob_storage_service','BlobStorageService'),
                              ('queue_service','QueueService'),('ai_plan_draft_service','AiPlanDraftService'),
                              ('pdf_service','PdfService'),('storage_asset_service','StorageAssetService')]:
                stack.enter_context(patch(f'services.{mod}.{name}'))
            spec=importlib.util.spec_from_file_location('access_test_app',foundations.ROOT/'mobility-ai-service/app.py')
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        module.ClientService=ClientService
        module.PlanService=PlanService
        module.JobService=JobService
        module.AiPlanDraftService=lambda repository, plans: AiPlanDraftService(repository,plans,generator=Mock())
        security=SecurityService(AuthConfig(secrets.token_urlsafe(32),24))
        module.auth_service=AuthService(PostgresPlatformRepository(self.config),security)
        # Exercise the protected media route independently of the default feature flag.
        # With analysis disabled, require_analysis intentionally returns 404 first.
        module.analysis_enabled=lambda: True
        module.storage_asset_service.get_progress_photo.return_value=(b'image','image/jpeg')
        module.pdf_service.render_simple_pdf.return_value=b'%PDF-test'
        def request(path,user=202,method='GET',body=None,organization=None,query=''):
            async def run():
                messages=[]
                raw=json.dumps(body).encode() if body else b''
                async def receive(): return {'type':'http.request','body':raw,'more_body':False}
                async def send(message): messages.append(message)
                headers=[(b'x-organization-id',str(organization or self.org).encode()),(b'content-type',b'application/json')]
                if user is not None: headers.append((b'authorization',('Bearer '+security.create_access_token(user_id=user,email='fixture')).encode()))
                await module.app({'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1','method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':query.encode(),'root_path':'','headers':headers,'client':('test',1),'server':('test',80)},receive,send)
                return next(m['status'] for m in messages if m['type']=='http.response.start')
            return asyncio.run(run())
        self.assertEqual(request('/clients'),200)
        self.assertEqual(request('/clients/102'),404)
        self.assertEqual(request('/clients',organization=self.other),403)
        self.assertEqual(request('/clients/101/nutrition-plans'),200)
        self.assertEqual(request('/nutrition-plans/1/pdf'),200)
        self.assertEqual(request('/clients/101/plan-drafts'),403)
        self.assertEqual(request('/clients/101',method='PUT',body={'first_name':'Forged','last_name':'Edit'}),403)
        self.assertEqual(request('/organization/people'),403)
        self.assertEqual(request('/organization/people',user=101),200)
        self.assertEqual(request('/frames/missing',user=None,query='token=bad'),401)
        self.assertEqual(request('/frames/missing'),404)
        with self.access(202) as repo: blob=repo.list_progress_photos(101)[0]['blob_name']
        self.assertEqual(request('/client-progress-photos/'+blob),200)
        module.storage_asset_service.get_progress_photo.reset_mock()
        self.assertEqual(request('/client-progress-photos/'+blob,user=102,organization=self.other),404)
        module.storage_asset_service.get_progress_photo.assert_not_called()
        self.assertEqual(request(f'/organization/people/{self.staff}/roles/trainer',user=101,method='DELETE'),200)
        self.assertEqual(request('/clients/101',user=201),404)

    def test_member_mode_preserves_self_access_without_staff_privileges(self):
        with self.connect(self.db,row_factory=dict_row) as c:
            repo=AccessRepository(c,self.org,201,member_mode=True)
            self.assertEqual([r['id'] for r in repo.list_clients()],[103])
            with self.assertRaises(ResourceNotFound): repo.fetch_client(101)
            with self.assertRaises(AccessDenied): repo.list_people()
            with self.assertRaises(AccessDenied): repo.add_client_goal({'client_id':103})

    def test_legacy_frame_backfill_quarantines_ambiguous_references(self):
        db='media_'+uuid.uuid4().hex[:10]
        self.create_database(db)
        self.flyway(db,'migrate','-target=4')
        with self.connect(db) as c:
            c.execute((foundations.ROOT/'database/tests/legacy_fixture.sql').read_text())
        self.flyway(db,'migrate','-target=5')
        with self.connect(db) as c:
            c.execute("UPDATE form_analyses SET result_json=%s::jsonb WHERE id='owned-analysis'",(json.dumps({'frames':[{'image_path':'/frames/unique.jpg?v=1'},{'image_path':'/frames/shared.jpg?v=2'}]}),))
            # Retained ownerless legacy data cannot be edited through V5 triggers;
            # install the synthetic conflicting reference only for this migration fixture.
            c.execute('ALTER TABLE form_analyses DISABLE TRIGGER scope_coaching_record')
            c.execute("UPDATE form_analyses SET result_json=%s::jsonb WHERE id='unowned-analysis'",(json.dumps({'frames':[{'image_path':'/frames/shared.jpg?v=3'}]}),))
            c.execute('ALTER TABLE form_analyses ENABLE TRIGGER scope_coaching_record')
        self.flyway(db,'migrate')
        self.flyway(db,'validate')
        self.flyway(db,'migrate')
        with self.connect(db) as c:
            self.assertEqual(c.execute('SELECT blob_name,analysis_id FROM form_analysis_assets').fetchall(),[('unique.jpg','owned-analysis')])
