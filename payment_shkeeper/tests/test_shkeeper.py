from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_shkeeper.controllers.main import SHKeeperController
from odoo.addons.payment_shkeeper.tests.common import SHKeeperCommon


SEND_API_REQUEST = (
    'odoo.addons.payment.models.payment_provider.PaymentProvider._send_api_request'
)


@tagged('post_install', '-at_install')
class TestSHKeeper(SHKeeperCommon, PaymentHttpCommon):

    def _render(self, tx, response=None):
        with patch(SEND_API_REQUEST, return_value=response or self.invoice_response) as mock:
            processing_values = tx._get_processing_values()
        return processing_values, mock

    def _post_webhook(self, payload, **sign_kwargs):
        body, headers = self._sign(payload, **sign_kwargs)
        url = self._build_url(SHKeeperController._webhook_url)
        return self.url_open(url, data=body, headers=headers, method='POST')

    def test_invoice_is_created_for_the_selected_crypto(self):
        tx = self._create_transaction('redirect')
        processing_values, mock = self._render(tx)

        method, endpoint = mock.call_args.args
        payload = mock.call_args.kwargs['json']
        self.assertEqual((method, endpoint), ('POST', '/BTC/payment_request'))
        self.assertEqual(payload['external_id'], tx.reference)
        self.assertEqual(payload['fiat'], 'USD')
        self.assertTrue(payload['callback_url'].endswith('/payment/shkeeper/webhook'))
        self.assertIn('redirect_form_html', processing_values)
        self.assertEqual(tx.shkeeper_address, self.invoice_response['wallet'])
        self.assertEqual(tx.shkeeper_amount_crypto, self.invoice_response['amount'])
        self.assertEqual(tx.provider_reference, '42')

    def test_status_page_shows_payment_instructions(self):
        tx = self._create_transaction('redirect')
        self._render(tx)
        self.env['payment.transaction']._process('shkeeper', {'reference': tx.reference})
        html = str(self.env['ir.qweb']._render('payment.state_header', {'tx': tx}))
        self.assertIn(self.invoice_response['wallet'], html)
        self.assertIn('/report/barcode/?barcode_type=QR', html)

    def test_partial_payment_asks_for_the_remaining_amount(self):
        tx = self._create_transaction('redirect')
        self._render(tx)
        self.env['payment.transaction']._process(
            'shkeeper', self._notification(status='PARTIAL', paid=False, balance_crypto='0.0001')
        )
        html = str(self.env['ir.qweb']._render('payment.state_header', {'tx': tx}))
        self.assertIn('Send the remaining amount to the same address.', html)

    def test_callback_base_url_override(self):
        self.provider.shkeeper_callback_base_url = 'https://shop.example.com/'
        self.assertEqual(
            self.provider._shkeeper_get_callback_url(),
            'https://shop.example.com/payment/shkeeper/webhook',
        )

    def test_gateway_error_sets_transaction_in_error(self):
        tx = self._create_transaction('redirect')
        self._render(tx, {'status': 'error', 'message': 'BTC payment gateway is unavailable'})
        self.assertEqual(tx.state, 'error')
        self.assertIn('unavailable', tx.state_message)

    def test_bitcoin_qr_code_uses_bip21(self):
        tx = self._create_transaction('redirect')
        self._render(tx)
        self.assertEqual(
            tx._shkeeper_get_payment_uri(),
            f"bitcoin:{self.invoice_response['wallet']}?amount={self.invoice_response['amount']}",
        )

    def test_return_from_checkout_sets_pending(self):
        tx = self._create_transaction('redirect')
        self.env['payment.transaction']._process('shkeeper', {'reference': tx.reference})
        self.assertEqual(tx.state, 'pending')

    def test_paid_notification_confirms_transaction(self):
        tx = self._create_transaction('redirect', state='pending')
        self.env['payment.transaction']._process('shkeeper', self._notification())
        self.assertEqual(tx.state, 'done')

    def test_overpaid_notification_confirms_transaction(self):
        tx = self._create_transaction('redirect', state='pending')
        self.env['payment.transaction']._process(
            'shkeeper', self._notification(status='OVERPAID', overpaid_fiat='1.00')
        )
        self.assertEqual(tx.state, 'done')

    def test_partial_notification_keeps_transaction_pending(self):
        tx = self._create_transaction('redirect', state='pending')
        self.env['payment.transaction']._process(
            'shkeeper', self._notification(status='PARTIAL', paid=False, balance_crypto='0.0001')
        )
        self.assertEqual(tx.state, 'pending')
        self.assertEqual(tx.shkeeper_balance_crypto, '0.0001')
        self.assertIn('Partial payment', tx.state_message)

    def test_currency_mismatch_sets_error(self):
        tx = self._create_transaction('redirect', state='pending')
        self.env['payment.transaction']._process('shkeeper', self._notification(fiat='EUR'))
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.payment_shkeeper.controllers.main')
    def test_webhook_accepts_signed_notification(self):
        tx = self._create_transaction('redirect', state='pending')
        response = self._post_webhook(self._notification())
        self.assertEqual(response.status_code, 202)
        self.assertEqual(tx.state, 'done')

    @mute_logger('odoo.addons.payment_shkeeper.controllers.main')
    def test_webhook_rejects_wrong_key(self):
        tx = self._create_transaction('redirect', state='pending')
        response = self._post_webhook(self._notification(), secret='wrong-key')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(tx.state, 'pending')

    @mute_logger('odoo.addons.payment_shkeeper.controllers.main')
    def test_webhook_rejects_tampered_body(self):
        tx = self._create_transaction('redirect', state='pending')
        body, headers = self._sign(self._notification(paid=False, status='PARTIAL'))
        tampered = body.replace(b'"paid":false', b'"paid":true').replace(b'PARTIAL', b'PAID')
        url = self._build_url(SHKeeperController._webhook_url)
        response = self.url_open(url, data=tampered, headers=headers, method='POST')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(tx.state, 'pending')

    @mute_logger('odoo.addons.payment_shkeeper.controllers.main')
    def test_webhook_rejects_expired_notification(self):
        tx = self._create_transaction('redirect', state='pending')
        response = self._post_webhook(self._notification(), timestamp=1)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(tx.state, 'pending')

    @mute_logger('odoo.addons.payment_shkeeper.controllers.main', 'odoo.addons.payment.models.payment_transaction')
    def test_webhook_acknowledges_unknown_reference(self):
        response = self._post_webhook(self._notification(external_id='unknown'))
        self.assertEqual(response.status_code, 202)
