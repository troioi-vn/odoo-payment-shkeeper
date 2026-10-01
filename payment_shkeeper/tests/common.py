import hashlib
import hmac
import json
import time

from odoo.addons.payment.tests.common import PaymentCommon


class SHKeeperCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.api_key = 'dummy-api-key'
        cls.shkeeper = cls._prepare_provider('shkeeper', update_values={
            'shkeeper_api_url': 'https://shkeeper.example.com',
            'shkeeper_api_key': cls.api_key,
        })

        cls.provider = cls.shkeeper
        cls.currency = cls.currency_usd
        cls.amount = 49.0
        cls.payment_method = cls.env.ref('payment_shkeeper.payment_method_shkeeper_btc')
        cls.payment_method_id = cls.payment_method.id
        cls.payment_method_code = cls.payment_method.code

        cls.invoice_response = {
            'status': 'success',
            'id': 42,
            'exchange_rate': '65000.00',
            'amount': '0.00075385',
            'wallet': 'bc1qexampleaddress0000000000000000000000',
            'recalculate_after': 0,
            'display_name': 'Bitcoin',
        }

    def _notification(self, status='PAID', paid=True, **values):
        return {
            'external_id': self.reference,
            'crypto': 'BTC',
            'addr': self.invoice_response['wallet'],
            'fiat': 'USD',
            'balance_fiat': '49',
            'balance_crypto': '0.00075385',
            'paid': paid,
            'status': status,
            'transactions': [],
            'fee_percent': '0',
            'overpaid_fiat': '0.00',
            **values,
        }

    def _sign(self, payload, secret=None, timestamp=None):
        """ Encode and sign the payload the way SHKeeper does. """
        secret = secret or self.api_key
        timestamp = int(time.time()) if timestamp is None else timestamp
        body = json.dumps(
            payload, separators=(',', ':'), sort_keys=True, ensure_ascii=False
        ).encode()
        signature = hmac.new(
            secret.encode(), f'{timestamp}.'.encode() + body, hashlib.sha256
        ).hexdigest()
        headers = {
            'Content-Type': 'application/json',
            'X-Shkeeper-Api-Key': secret,
            'X-Shkeeper-Timestamp': str(timestamp),
            'X-Shkeeper-Signature': signature,
        }
        return body, headers
