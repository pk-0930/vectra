"""Published gym catalogues and immutable, unpaid onboarding requests."""
from io import BytesIO
from contextlib import nullcontext
import hashlib
import json
import re
import warnings
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from repositories.access_repository import AccessDenied, ResourceNotFound
from services.email_delivery_service import public_web_url

MAX_IMAGE_BYTES = 2 * 1024 * 1024
DEFAULT_CONFIG = {'display_name': '', 'description': '', 'address': '', 'contact_phone': '',
                  'logo_id': None, 'registration_enabled': False, 'plans': [],
                  'payment': {'recipient_name': '', 'upi_id': '', 'qr_asset_id': None}}


class CatalogueChanged(ValueError):
    pass


def clean_image(raw):
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError('Upload a PNG or JPEG image up to 2 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in {'PNG', 'JPEG'} or getattr(source, 'n_frames', 1) != 1:
                    raise ValueError('Only single-frame PNG and JPEG images are supported.')
                if min(source.size) < 64 or max(source.size) > 4096 or source.width * source.height > 8_000_000:
                    raise ValueError('Image dimensions must be 64–4096 pixels, at most 8 megapixels.')
                source.load()
                # Strip metadata, animation, executable payloads and orientation ambiguity.
                oriented = ImageOps.exif_transpose(source).convert('RGBA')
                image = Image.new('RGB', oriented.size, 'white')
                image.paste(oriented, mask=oriented.getchannel('A'))
                output = BytesIO()
                image.save(output, format='PNG', optimize=True)
        result = output.getvalue()
        if len(result) > MAX_IMAGE_BYTES:
            raise ValueError('The normalized image exceeds 2 MB. Use a smaller image.')
        return result
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('The image could not be safely decoded. Upload a PNG or JPEG.') from None


def validate_config(config):
    def text(key, maximum, required=False, source=None):
        value = (source or config).get(key, '')
        if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
            raise ValueError(f'Enter a valid {key.replace("_", " ")}.')
        return value.strip()

    payment = config.get('payment', {})
    if not isinstance(payment, dict):
        raise ValueError('Enter payment details.')
    upi = text('upi_id', 120, source=payment)
    if upi and not re.fullmatch(r'[A-Za-z0-9._-]{2,100}@[A-Za-z0-9.-]{2,30}', upi):
        raise ValueError('Enter a valid UPI ID.')
    result = {key: text(key, size, key == 'display_name') for key, size in
              [('display_name', 120), ('description', 1200), ('address', 500), ('contact_phone', 40)]}
    if type(config.get('registration_enabled')) is not bool:
        raise ValueError('Select a registration availability setting.')
    result.update(logo_id=config.get('logo_id'), registration_enabled=config['registration_enabled'], plans=[],
                  payment={'recipient_name': text('recipient_name', 120, source=payment), 'upi_id': upi,
                           'qr_asset_id': payment.get('qr_asset_id')})
    plans = config.get('plans')
    if not isinstance(plans, list) or len(plans) > 100:
        raise ValueError('A catalogue can contain up to 100 plans.')
    seen = set()
    for plan in plans:
        if not isinstance(plan, dict):
            raise ValueError('Invalid plan.')
        try:
            identifier = str(UUID(str(plan['id'])))
        except (ValueError, KeyError):
            raise ValueError('Each plan needs a unique identifier.') from None
        if identifier in seen:
            raise ValueError('Plan identifiers must be unique.')
        seen.add(identifier)
        kind = plan.get('kind')
        months = plan.get('duration_months')
        sessions = plan.get('sessions')
        if (kind not in {'gym', 'pt'} or type(plan.get('amount_paise')) is not int
                or not 0 < plan['amount_paise'] <= 100_000_000 or type(plan.get('active')) is not bool):
            raise ValueError('Plans need a type, positive integer paise price and availability.')
        if not ((type(months) is int and months in {1, 3, 6, 12} and sessions is None)
                or (kind == 'pt' and months is None and sessions == 1 and type(sessions) is int)):
            raise ValueError('Use 1, 3, 6 or 12 months, or one PT session.')
        trainer = plan.get('trainer_relationship_id')
        if kind == 'pt' and (type(trainer) is not int or trainer <= 0):
            raise ValueError('Select a trainer for each PT plan.')
        result['plans'].append({'id': identifier, 'kind': kind, 'name': text('name', 120, True, plan),
                                'terms': text('terms', 2000, True, plan), 'amount_paise': plan['amount_paise'],
                                'duration_months': months, 'sessions': sessions, 'active': plan['active'],
                                'trainer_relationship_id': trainer if kind == 'pt' else None,
                                'trainer_name': text('trainer_name', 120, kind == 'pt', plan) if kind == 'pt' else ''})
    for value in [result['logo_id'], result['payment']['qr_asset_id']]:
        if value is not None:
            try:
                UUID(str(value))
            except ValueError:
                raise ValueError('Upload an image before saving.') from None
    if result['registration_enabled'] and (not any(p['active'] and p['kind'] == 'gym' for p in result['plans'])
            or not all(result['payment'].values())):
        raise ValueError('Publish at least one gym plan and confirm all payment details before enabling registration.')
    return result


class GymService:
    def __init__(self, repository, billing):
        self.repository = repository
        self.billing = billing

    @staticmethod
    def require_admin(access):
        access.require_admin()
        if access.context['organization_type'] != 'gym':
            raise AccessDenied('Gym setup is available only in gym businesses.')

    def setup(self, access):
        self.require_admin(access)
        # GET does not create a profile, so read-only billing remains genuinely read-only.
        db, org = access.connection, access.organization_id
        row = self.repository.profile(db, org)
        config = row['configuration'] if row else dict(DEFAULT_CONFIG)
        try:
            join_url = self.join_url(row) if row else None
        except ValueError:
            join_url = None
        return {'revision': row['revision'] if row else 0, 'configuration': config,
                'public_id': row['public_id'] if row else None,
                'join_url': join_url,
                'trainers': self.repository.trainers(db, org), 'can_edit_payment': 'owner' in access.roles,
                'audit': self.repository.audit(db, org)}

    @staticmethod
    def join_url(row):
        return f'{public_web_url()}/join/{row["public_id"]}'

    def save(self, access, expected_revision, config, confirm_payment):
        self.require_admin(access)
        config = validate_config(config)
        db, org = access.connection, access.organization_id
        row = self.repository.ensure_profile(db, org)
        if row['revision'] != expected_revision:
            raise CatalogueChanged('Gym setup changed. Reload and review the latest version before saving.')
        old = row['configuration'].get('payment', DEFAULT_CONFIG['payment'])
        if config['payment'] != old:
            if 'owner' not in access.roles:
                raise AccessDenied('Only the gym owner can change the payment destination.')
            if not confirm_payment:
                raise ValueError('Preview and confirm the recipient, UPI ID and payment QR before saving.')
        trainers = {r['id'] for r in self.repository.trainers(db, org)}
        if any(p['active'] and p['kind'] == 'pt' and p['trainer_relationship_id'] not in trainers for p in config['plans']):
            raise ValueError('An active PT plan must belong to a currently active trainer in this gym.')
        for asset_id, kind in [(config['logo_id'], 'logo'), (config['payment']['qr_asset_id'], 'payment_qr')]:
            if asset_id and not self.repository.asset_matches(db, asset_id, org, kind):
                raise ValueError('This image does not belong to this gym or image type.')
        self.repository.save_profile(db, org, access.user_id, row['revision'] + 1, config)
        return self.setup(access)

    def upload(self, access, kind, raw):
        self.require_admin(access)
        if kind not in {'logo', 'payment_qr'}:
            raise ValueError('Unsupported image type.')
        if kind == 'payment_qr' and 'owner' not in access.roles:
            raise AccessDenied('Only the gym owner can upload a payment QR.')
        png = clean_image(raw)
        db = access.connection
        self.repository.ensure_profile(db, access.organization_id)
        # Bound abandoned drafts; published and historical images are never overwritten.
        count = self.repository.recent_upload_count(db, access.organization_id)
        if count >= 30:
            raise ValueError('Upload limit reached. Try again in an hour.')
        identifier = uuid4()
        self.repository.insert_asset(db, identifier, access.organization_id, kind, png, access.user_id)
        return {'id': identifier}

    def asset(self, asset_id, access=None):
        with (nullcontext(access.connection) if access is not None else self.repository.transaction()) as db:
            row = self.repository.asset(db, asset_id)
            if not row:
                raise ResourceNotFound('Image not found.')
            if access is not None:
                self.require_admin(access)
                if row['organization_id'] != access.organization_id:
                    raise ResourceNotFound('Image not found.')
            else:
                # Draft images are private; published and frozen purchase images remain readable.
                published = self.repository.asset_published(db, asset_id, row['organization_id'])
                if not published:
                    raise ResourceNotFound('Image not found.')
            return bytes(row['png'])

    def available(self, db, row):
        if not row:
            return 'not_found'
        org = self.repository.organization(db, row['organization_id'])
        if org['status'] != 'active' or org['organization_type'] != 'gym':
            return 'inactive'
        if self.billing.state(db, org['id'])['access'] not in {'active', 'legacy', 'grace'}:
            return 'subscription_unavailable'
        if not row['configuration'].get('registration_enabled'):
            return 'paused'
        rollout = db.execute('SELECT purchases_enabled FROM business_web_rollout WHERE organization_id=%s',
                             (row['organization_id'],)).fetchone()
        if rollout and rollout['purchases_enabled'] is False:
            return 'paused'
        return None

    def catalogue(self, db, row):
        config = row['configuration']
        trainers = {r['id'] for r in self.repository.trainers(db, row['organization_id'])}
        plans = [{k: v for k, v in p.items() if k not in {'trainer_relationship_id', 'active'}}
                 for p in config['plans'] if p['active'] and (p['kind'] == 'gym' or p['trainer_relationship_id'] in trainers)]
        return {'public_id': row['public_id'], 'revision': row['revision'],
                **{k: config[k] for k in ('display_name', 'description', 'address', 'contact_phone', 'logo_id', 'payment')},
                'plans': plans}

    def public(self, public_id):
        with self.repository.transaction() as db:
            row = self.repository.public_profile(db, public_id)
            reason = self.available(db, row)
            if reason:
                return {'available': False, 'reason': reason}
            return {'available': True, **self.catalogue(db, row)}

    def history(self, public_id, user):
        with self.repository.transaction() as db:
            row = self.repository.public_profile(db, public_id)
            if not row:
                raise ResourceNotFound('Gym not found.')
            rows = self.repository.purchases(db, row['organization_id'], user['id'])
            return [self.purchase_view(p, row['revision']) for p in rows]

    @staticmethod
    def purchase_view(row, revision):
        return {k: row[k] for k in ('id', 'snapshot', 'amount_paise', 'currency', 'status', 'created_at')} | {
            'needs_review': row['profile_revision'] != revision}

    def join(self, public_id, user, payload):
        if user.get('verification_required'):
            raise AccessDenied('Verify your email before submitting your registration.')
        if payload.get('accept_terms') is not True:
            raise ValueError('Review and accept the selected plan terms and payment instructions.')
        # Lock order: profile, organization, relationship, purchase. One gym's edits and joins serialize.
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        with self.repository.transaction() as db:
            row = self.repository.public_profile(db, public_id, lock=True)
            reason = self.available(db, row)
            if reason:
                raise ValueError('Registration is unavailable. Contact the gym or try again later.')
            org = row['organization_id']
            relationship = self.repository.ensure_relationship(db, (org, user['id']))
            if relationship['status'] != 'active':
                raise AccessDenied('Your relationship with this gym is inactive. Contact the gym owner.')
            previous = self.repository.purchase_request(db, org, relationship['id'], payload['request_id'])
            if previous:
                if previous['request_hash'] != digest:
                    raise ValueError('This request was already used. Reload before submitting a different registration.')
                return self.purchase_view(previous, row['revision'])
            if row['revision'] != payload['revision']:
                raise CatalogueChanged('The catalogue or payment instructions changed. Refresh and review before continuing.')
            catalogue = self.catalogue(db, row)
            ids = payload['plan_ids']
            selected = [p for p in catalogue['plans'] if p['id'] in ids]
            if len(set(ids)) != len(ids) or len(selected) != len(ids) or sum(p['kind'] == 'gym' for p in selected) > 1 or sum(p['kind'] == 'pt' for p in selected) > 1:
                raise ValueError('Choose one gym plan, one PT plan, or one of each.')
            gym = next((p for p in selected if p['kind'] == 'gym'), None)
            if gym and any(p['kind'] == 'pt' and p['duration_months'] and p['duration_months'] > gym['duration_months'] for p in selected):
                raise ValueError('PT duration cannot exceed the selected gym membership duration.')
            replaces = payload.get('replaces_id')
            if replaces:
                old = self.repository.lock_purchase(db, replaces, org, relationship['id'])
                if not old or old['status'] != 'pending':
                    raise ValueError('Only your own pending registration can be refreshed.')
                self.repository.supersede(db, replaces)
            # Preserve the internal trainer reference for later activation; public discovery omits it.
            for plan in selected:
                plan['trainer_relationship_id'] = next(p['trainer_relationship_id'] for p in row['configuration']['plans'] if p['id'] == plan['id'])
            from repositories.pt_repository import PtRepository
            from services.pt_service import PtService, PT_TERMS
            from services.membership_service import today_india
            pt_service = PtService(PtRepository(self.repository.config))
            pt_plan = next((p for p in selected if p['kind'] == 'pt'), None)
            if pt_plan:
                # Pending gym payment is not paid coverage. Existing coverage is
                # checked again at verification, including after reservation expiry.
                pt_service.check(db, org, relationship['id'], pt_plan, today_india())
            snapshot = {'gym_name': catalogue['display_name'], 'public_id': str(public_id), 'plans': selected,
                        'payment': catalogue['payment'], 'member_name': payload['member_name'].strip(),
                        'mobile': payload['mobile'].strip(), 'terms': 'Pending registration only. No paid gym membership, PT entitlement or trainer capacity is granted. The gym must verify payment before activation. Fixed-duration plans do not auto-renew.'}
            if not snapshot['member_name'] or not re.fullmatch(r'\+?[0-9 ()-]{7,25}', snapshot['mobile']):
                raise ValueError('Enter your name and a valid contact phone number.')
            if pt_plan:
                snapshot['pt_service_terms'] = PT_TERMS
                snapshot['terms'] = 'Pending purchase; no paid entitlement until receipt verification. Trainer slot reserved for 24 hours only. Check with reception before paying after reservation expiry. PT: 60 minutes per appointment; duration packages allow one session per day. Single-session credit expires after 30 days or earlier gym expiry. Only completion consumes credit; cancellation does not. Reassignment requires member consent. Fixed duration; no auto-renewal.'
            total = sum(p['amount_paise'] for p in selected)
            created = self.repository.insert_purchase(db, org, relationship['id'], payload['request_id'],
                                                      digest, row['revision'], snapshot, total, replaces)
            if pt_plan:
                pt_service.repository.reserve(db, created, pt_plan['trainer_relationship_id'])
            return self.purchase_view(created, row['revision'])
