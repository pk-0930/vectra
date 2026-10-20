import copy
from io import BytesIO
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4
import cv2
import numpy as np
from PIL import Image
from services.gym_service import clean_image, validate_config, DEFAULT_CONFIG
from services.gym_registration_media import registration_qr, reception_poster
from services.identity_service import IdentityService


def configuration():
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.update(display_name='Fixture Gym', plans=[{
        'id': str(uuid4()), 'kind': 'gym', 'name': 'Monthly', 'terms': 'One month. Manual renewal.',
        'amount_paise': 12345, 'duration_months': 1, 'sessions': None, 'active': True,
        'trainer_relationship_id': None, 'trainer_name': '',
    }])
    return config


class GymValidationTests(TestCase):
    def test_plan_prices_are_integer_paise_and_duration_is_fixed(self):
        config = configuration()
        self.assertEqual(validate_config(config)['plans'][0]['amount_paise'], 12345)
        for value in [True, 12.34, '12345', 0, -1, 100_000_001]:
            config['plans'][0]['amount_paise'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): validate_config(config)
        config['plans'][0]['amount_paise'] = 12345
        for value in [2, 4, 24, True, '1']:
            config['plans'][0]['duration_months'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): validate_config(config)

    def test_pt_per_session_and_trainer_are_required(self):
        config = configuration()
        p = config['plans'][0]
        p.update(kind='pt', duration_months=None, sessions=1, trainer_relationship_id=5, trainer_name='Public trainer')
        self.assertEqual(validate_config(config)['plans'][0]['sessions'], 1)
        for patch in [{'trainer_relationship_id': None}, {'sessions': 10}, {'trainer_name': ''}]:
            invalid = copy.deepcopy(config); invalid['plans'][0].update(patch)
            with self.subTest(patch=patch), self.assertRaises(ValueError): validate_config(invalid)

    def test_publication_requires_payment_and_active_gym_plan(self):
        config = configuration(); config['registration_enabled'] = True
        with self.assertRaises(ValueError): validate_config(config)
        config['payment'] = {'recipient_name': 'Gym', 'upi_id': 'gym@bank', 'qr_asset_id': str(uuid4())}
        self.assertTrue(validate_config(config)['registration_enabled'])
        config['plans'][0]['active'] = False
        with self.assertRaises(ValueError): validate_config(config)

    def test_duplicate_ids_and_invalid_upi_rejected(self):
        config = configuration(); config['plans'] *= 2
        with self.assertRaises(ValueError): validate_config(config)
        config = configuration(); config['payment']['upi_id'] = 'https://attacker.invalid'
        with self.assertRaises(ValueError): validate_config(config)

    def test_upload_bytes_decoded_and_reencoded_without_metadata(self):
        from PIL.PngImagePlugin import PngInfo
        source = BytesIO(); meta = PngInfo(); meta.add_text('private', 'remove me')
        Image.new('RGB', (100, 100), 'white').save(source, 'PNG', pnginfo=meta)
        result = clean_image(source.getvalue() + b'untrusted trailing bytes')
        self.assertNotIn(b'remove me', result); self.assertNotIn(b'untrusted', result)
        for raw in [b'', b'<svg></svg>', b'a' * (2 * 1024 * 1024 + 1)]:
            with self.assertRaises(ValueError): clean_image(raw)
        source = BytesIO(); Image.new('RGB', (5000, 64)).save(source, 'PNG')
        with self.assertRaises(ValueError): clean_image(source.getvalue())

    def test_transparent_upload_is_composited_on_white(self):
        source = BytesIO()
        Image.new('RGBA', (100, 100), (0, 0, 0, 0)).save(source, 'PNG')
        result = Image.open(BytesIO(clean_image(source.getvalue())))
        self.assertEqual(result.getpixel((50, 50)), (255, 255, 255))

    def test_qr_decodes_exact_registration_url_and_poster_is_pdf(self):
        url = 'https://gym.example.invalid/join/' + str(uuid4())
        png = registration_qr(url)
        pixels = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(pixels)
        self.assertEqual(decoded, url)
        self.assertTrue(reception_poster('Fixture Gym', url).startswith(b'%PDF'))

    def test_member_signup_enqueues_verification_without_coach_or_business(self):
        repo, security = MagicMock(), MagicMock()
        db = repo.transaction.return_value.__enter__.return_value
        repo.find_user_id.return_value = None
        repo.insert_identity.return_value = {'id': 99, 'session_version': 0}
        security.config.token_secret = 'test-only-secret-long-enough-for-signing'
        service = IdentityService(repo, security)
        user = service.register_member({'email': ' MEMBER@EXAMPLE.COM ', 'password': 'long-password-for-test'})
        self.assertEqual(user['id'], 99)
        repo.insert_identity.assert_called_once_with(db, ('member@example.com', security.hash_password.return_value))
        repo.insert_delivery.assert_called_once(); repo.insert_coach_profile.assert_not_called()
        repo.provision_coach_business.assert_not_called()
        repo.find_user_id.return_value = {'id': 99}
        with self.assertRaises(ValueError): service.register_member({'email': 'member@example.com', 'password': 'long-password-for-test'})
