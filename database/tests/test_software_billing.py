"""Step 4 real DB transactions with a synthetic Razorpay boundary."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

import test_organization_foundations as foundations
sys.path.insert(0,str(foundations.ROOT/'mobility-ai-service'))
sys.path.insert(0,str(foundations.ROOT/'mobility-ai-service/tests'))
from billing_fixtures import PLAN, FakeRazorpay, config
from config.postgres_config import PostgresConfig
from repositories.billing_repository import BillingRepository
from repositories.access_repository import AccessDenied
from services.billing_service import BillingService
from services.razorpay_service import ProviderError


@unittest.skipUnless(foundations.ENABLED,'Set VECTRA_RUN_MIGRATION_TESTS=1')
class SoftwareBillingTests(foundations.DisposablePostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_database('billing')
        cls.flyway('billing','migrate')
        cls.config=PostgresConfig(host='127.0.0.1',port=cls.port,dbname='billing',user='postgres',password=cls.password,sslmode='disable')

    def setUp(self):
        self.repo=BillingRepository(self.config)
        self.provider=FakeRazorpay()
        self.service=BillingService(self.repo,config(),self.provider)
        with self.repo.transaction() as db:
            # Other tests' records remain for uniqueness checks, but are not due for work.
            db.execute("UPDATE software_subscriptions SET next_sync_at=now()+interval '1 day'")
            self.user=db.execute("INSERT INTO users(email,password_hash,created_at,updated_at,verification_required,email_verified_at) "
                "VALUES(%s,'fixture',now(),now(),false,now()) RETURNING *",(uuid4().hex+'@example.invalid',)).fetchone()
        self.request=uuid4()
        self.org=self.service.create_business(self.user,self.request,'Fixture Gym','gym')['organization_id']

    def start(self):
        return self.service.start_subscription(self.user,self.org,'gym-monthly','software-v1')

    def current(self):
        with self.repo.transaction() as db:return self.repo.subscriptions(db,self.org,'test')[0]

    def sync(self):
        self.service.refresh(self.user,self.org)
        self.assertTrue(self.service.process_one())
        return self.service.summary(self.user,self.org)

    def create_remote(self):
        self.start(); self.assertTrue(self.service.process_one())
        return self.current()['provider_id']

    def test_fresh_upgrade_preserves_legacy_and_new_business_pending(self):
        self.assertEqual(self.service.summary(self.user,self.org)['access'],'pending')
        self.create_database('billing_upgrade');self.flyway('billing_upgrade','migrate','-target=7')
        with self.connect('billing_upgrade') as db:
            db.execute("INSERT INTO organizations(name,organization_type) VALUES('Existing','coaching')")
        self.flyway('billing_upgrade','migrate');self.flyway('billing_upgrade','validate')
        with self.connect('billing_upgrade') as db:
            self.assertFalse(db.execute('SELECT billing_required FROM organizations').fetchone()[0])
            self.assertTrue(db.execute("INSERT INTO organizations(name,organization_type) VALUES('New','gym') RETURNING billing_required").fetchone()[0])

    def test_onboarding_and_checkout_retries_are_idempotent_concurrently(self):
        self.assertEqual(self.service.create_business(self.user,self.request,'Fixture Gym','gym')['organization_id'],self.org)
        with self.assertRaises(ValueError):self.service.create_business(self.user,self.request,'Changed','gym')
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(lambda _:self.start(),range(2)))
        self.assertEqual(rows[0]['id'],rows[1]['id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.service.process_one(),range(2)))
        self.assertEqual(sorted(results),[False,True])
        self.assertEqual(self.provider.create_calls,1)

    def test_authorization_only_never_activates_then_verified_payment_activates_once(self):
        provider_id=self.create_remote()
        self.provider.charge(provider_id,authorization=True)
        self.assertEqual(self.sync()['access'],'pending')
        self.provider.charge(provider_id)
        first=self.sync()
        self.assertEqual(first['access'],'active');self.assertEqual(len(first['payments']),1)
        again=self.sync()
        self.assertEqual(again['paid_through'],first['paid_through']);self.assertEqual(len(again['payments']),1)
        with self.repo.transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM billing_notifications WHERE organization_id=%s',(self.org,)).fetchone()['n'],1)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM email_outbox e JOIN billing_notifications n ON n.id=e.billing_notification_id WHERE n.organization_id=%s',(self.org,)).fetchone()['n'],1)

    def test_mismatch_cannot_activate_and_rolls_back_partial_invoice_batch(self):
        provider_id=self.create_remote()
        self.provider.charge(provider_id)
        _,payment=self.provider.charge(provider_id)
        payment['amount']=1
        summary=self.sync()
        self.assertEqual(summary['access'],'pending');self.assertEqual(summary['payments'],[])
        self.assertEqual(summary['subscription']['error_code'],'payment_verification_mismatch')

    def test_failed_renewal_grace_expiry_and_recovery(self):
        provider_id=self.create_remote()
        self.provider.charge(provider_id,start=datetime.now(UTC)-timedelta(days=31))
        self.provider.remote[provider_id]['status']='pending'
        self.assertEqual(self.sync()['access'],'grace')
        with self.repo.transaction() as db:
            db.execute("UPDATE software_subscriptions SET plan_snapshot=jsonb_set(plan_snapshot,'{grace_days}','0') WHERE organization_id=%s",(self.org,))
        self.assertEqual(self.service.summary(self.user,self.org)['access'],'read_only')
        self.provider.charge(provider_id)
        self.assertEqual(self.sync()['access'],'active')

    def test_cancellation_preserves_history_and_reactivation_schedules_after_paid_end(self):
        provider_id=self.create_remote();self.provider.charge(provider_id)
        paid=self.sync()
        self.service.cancel(self.user,self.org);self.sync();self.sync()
        self.assertEqual(self.provider.cancel_calls,1)
        self.assertTrue(self.current()['cancel_confirmed'])
        self.assertEqual(self.service.summary(self.user,self.org)['access'],'active')
        self.provider.remote[provider_id]['status']='cancelled';self.sync()
        new=self.start()
        self.assertNotEqual(new['provider_id'],provider_id)
        self.assertEqual(self.current()['start_at'],paid['paid_through'])
        self.assertEqual(len(self.service.summary(self.user,self.org)['payments']),1)

    def test_ambiguous_creation_is_discovered_not_posted_twice(self):
        self.provider.ambiguous_create=True
        self.start();self.service.process_one()
        self.assertEqual(self.current()['status'],'creation_unknown')
        self.sync()
        self.assertEqual(self.current()['status'],'created')
        self.assertEqual(self.provider.create_calls,1)

    def test_provider_failure_before_creation_closes_failed_attempt(self):
        self.provider.plan_mismatch=True
        self.start();self.service.process_one()
        self.assertEqual(self.current()['status'],'creation_failed')
        self.assertEqual(self.provider.create_calls,0)
        self.service.refresh(self.user,self.org)
        self.assertFalse(self.service.process_one())
        self.assertEqual(self.current()['status'],'creation_failed')
        self.provider.plan_mismatch=False
        self.create_remote()
        self.assertEqual(self.provider.create_calls,1)

    def test_duplicate_and_out_of_order_events_use_current_provider_state(self):
        provider_id=self.create_remote();self.provider.charge(provider_id)
        def event(kind,event_id):
            raw=json.dumps({'event':kind,'payload':{'subscription':{'entity':{'id':provider_id,'status':'cancelled'}}}}).encode()
            sig=hmac.new(config().webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
            return self.service.webhook(raw,sig,event_id)
        event('subscription.charged','event-'+provider_id)
        event('subscription.charged','event-'+provider_id)
        with self.assertRaises(ValueError):event('subscription.pending','event-'+provider_id)
        self.service.process_one()
        self.assertEqual(self.current()['status'],'active')
        event('subscription.pending','older-'+provider_id)
        self.service.process_one()
        self.assertEqual(self.current()['status'],'active')
        self.assertEqual(len(self.service.summary(self.user,self.org)['payments']),1)

    def test_cross_business_and_nonowner_billing_are_forbidden(self):
        with self.repo.transaction() as db:
            other=db.execute("INSERT INTO users(email,password_hash,created_at,updated_at,verification_required) VALUES(%s,'fixture',now(),now(),false) RETURNING *",(uuid4().hex+'@example.invalid',)).fetchone()
        with self.assertRaises(AccessDenied):self.service.summary(other,self.org)
        with self.repo.transaction() as db:
            rel=db.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,%s) RETURNING id',(self.org,other['id'])).fetchone()['id']
            db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'admin')",(self.org,rel))
        self.assertNotIn('payments',self.service.summary(other,self.org))
        for method,args in [(self.service.start_subscription,('gym-monthly','software-v1')),(self.service.cancel,())]:
            with self.assertRaises(AccessDenied):method(other,self.org,*args)
        with self.assertRaises(ValueError):self.service.start_subscription(self.user,self.org,'coach-monthly','software-v1')

    def test_full_refund_removes_period_partial_refund_preserves_it(self):
        provider_id=self.create_remote();_,payment=self.provider.charge(provider_id)
        self.sync();payment['amount_refunded']=5000
        self.assertEqual(self.sync()['access'],'active')
        payment['amount_refunded']=10000;payment['status']='refunded'
        result=self.sync();self.assertEqual(result['access'],'read_only');self.assertEqual(result['payments'][0]['refunded_paise'],10000)
        payment['amount_refunded']=0;payment['status']='captured'
        self.assertEqual(self.sync()['payments'][0]['refunded_paise'],10000)

    def test_invalid_checkout_signature_does_not_schedule_or_grant_access(self):
        provider_id=self.create_remote()
        with self.assertRaises(ValueError):self.service.refresh(self.user,self.org,dict(razorpay_subscription_id=provider_id,razorpay_payment_id='pay_fake',razorpay_signature='bad'))
        raw=f'pay_fake|{provider_id}'.encode()
        signature=hmac.new(config().key_secret.encode(),raw,hashlib.sha256).hexdigest()
        self.service.refresh(self.user,self.org,dict(razorpay_subscription_id=provider_id,razorpay_payment_id='pay_fake',razorpay_signature=signature))
        self.assertEqual(self.service.summary(self.user,self.org)['access'],'pending')

    def test_payment_and_owner_notice_commit_atomically(self):
        provider_id=self.create_remote();self.provider.charge(provider_id)
        self.service.refresh(self.user,self.org)
        with patch.object(self.repo, 'notify_owners', side_effect=RuntimeError('notification unavailable')):
            self.service.process_one()
        self.assertEqual(self.service.summary(self.user,self.org)['payments'],[])
        self.assertEqual(self.sync()['access'],'active')
        with self.repo.transaction() as db:
            notices=db.execute('SELECT count(*) AS count FROM billing_notifications WHERE organization_id=%s', (self.org,)).fetchone()
        self.assertGreater(notices['count'],0)

    def test_missing_webhook_is_repaired_by_periodic_reconciliation(self):
        provider_id=self.create_remote();self.provider.charge(provider_id)
        with self.repo.transaction() as db:db.execute('UPDATE software_subscriptions SET next_sync_at=now() WHERE organization_id=%s',(self.org,))
        self.service.process_one()
        self.assertEqual(self.service.summary(self.user,self.org)['access'],'active')

    def test_cancelling_before_provider_creation_does_not_create_remote(self):
        self.start();self.service.cancel(self.user,self.org);self.service.process_one()
        self.assertEqual(self.current()['status'],'cancelled')
        self.assertEqual(self.provider.create_calls,0)
        self.service.refresh(self.user,self.org)
        self.assertFalse(self.service.process_one())
        self.assertEqual(self.current()['status'],'cancelled')

    def test_test_payments_do_not_grant_live_mode_access(self):
        from dataclasses import replace
        provider_id=self.create_remote();self.provider.charge(provider_id);self.sync()
        live=BillingService(self.repo,replace(config(),mode='live',key_id='rzp_live_fixture'),self.provider)
        self.assertEqual(live.summary(self.user,self.org)['access'],'pending')
        self.assertEqual(live.summary(self.user,self.org)['payments'],[])

    def test_http_business_registration_verification_and_billing_gate(self):
        import asyncio
        from config.auth_config import AuthConfig
        from services.auth_service import AuthService
        from services.identity_service import IdentityService
        from services.security_service import SecurityService
        from test_auth_routes import AuthRouteTests
        AuthRouteTests.setUpClass()
        module=AuthRouteTests.module
        security=SecurityService(AuthConfig('isolated-billing-test-signing-key-value',24))
        module.auth_service=AuthService(self.repo,security)
        module.identity_service=IdentityService(self.repo,security)
        module.billing_service=self.service
        module.client_service.create_client.return_value = dict(id=1,coach_id=1,first_name='Allowed',last_name='Write',dob=None,gender=None,height_cm=None,weight_kg=None,is_active=True,current_goal_type=None,current_goal_notes=None,created_at='2026-10-18',updated_at='2026-10-18')
        def request(path,data=None,token=None,method='POST',org=None):
            async def run():
                messages=[]
                async def receive():return {'type':'http.request','body':json.dumps(data or {}).encode(),'more_body':False}
                async def send(message):messages.append(message)
                headers=[(b'content-type',b'application/json'),(b'x-organization-id',str(org or self.org).encode())]
                if token:headers.append((b'authorization',f'Bearer {token}'.encode()))
                await module.app({'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1',
                    'method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'',
                    'root_path':'','headers':headers,'client':('billing-fixture',1),'server':('test',80)},receive,send)
                return next(m['status'] for m in messages if m['type']=='http.response.start'),json.loads(b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'))
            return asyncio.run(run())
        email=uuid4().hex+'@example.invalid'
        status,registered=request('/auth/register-business',dict(email=email,password='long-fixture-password',business_name='New Online Coach',business_type='coaching',request_id=str(uuid4())))
        self.assertEqual(status,200)
        self.assertIsNone(registered['coach'])
        self.assertEqual(registered['organizations'][0]['organization_type'],'coaching')
        new_org=registered['organizations'][0]['organization_id']
        self.assertEqual(request('/clients',token=registered['access_token'],method='GET',org=new_org)[0],403)
        with self.repo.transaction() as db:action=db.execute("SELECT id FROM identity_actions WHERE email=%s AND kind='verify'",(email,)).fetchone()
        request('/auth/email/verify/confirm',{'token':module.identity_service.token(action['id'])})
        self.assertEqual(request('/clients',token=registered['access_token'],method='GET',org=new_org)[0],402)
        token=security.create_access_token(user_id=self.user['id'],email=self.user['email'])
        self.assertEqual(request(f'/organizations/{self.org}/billing',token=token,method='GET')[0],200)
        self.assertEqual(request(f'/organizations/{self.org}/billing/checkout',dict(plan_code='gym-monthly',terms_version='software-v1',accept_terms=False),token)[0],400)
        self.assertEqual(request(f'/organizations/{self.org}/billing/checkout',dict(plan_code='gym-monthly',terms_version='software-v1',accept_terms=True),token)[0],200)
        self.service.process_one();provider_id=self.current()['provider_id']
        self.provider.charge(provider_id,start=datetime.now(UTC)-timedelta(days=40));self.sync()
        self.assertEqual(request('/clients',token=token,method='GET')[0],200)
        self.assertEqual(request('/clients',{'first_name':'Blocked','last_name':'Write'},token)[0],402)
        self.provider.charge(provider_id);self.sync()
        self.assertEqual(request('/clients',{'first_name':'Allowed','last_name':'Write'},token)[0],200)
