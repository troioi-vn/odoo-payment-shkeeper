import hashlib
import hmac
import json
import pprint
import time

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.payment_shkeeper import const


_logger = get_payment_logger(__name__)


class SHKeeperController(http.Controller):
    _return_url = '/payment/shkeeper/return'
    _webhook_url = '/payment/shkeeper/webhook'

    @http.route(_return_url, type='http', auth='public', methods=['POST'], csrf=False)
    def shkeeper_return_from_checkout(self, **data):
        """ Mark the transaction as awaiting payment and show the payment instructions.

        The redirect form posts only the reference, so this route cannot confirm a payment; it can
        only move a draft transaction to pending.
        """
        _logger.info("Handling redirection from the payment form with data:\n%s", pprint.pformat(data))
        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference(
            'shkeeper', {'reference': data.get('reference')}
        )
        if tx_sudo:
            tx_sudo._process('shkeeper', {'reference': tx_sudo.reference})
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False)
    def shkeeper_webhook(self):
        """ Process the payment notification sent by SHKeeper.

        SHKeeper retries a notification until it receives HTTP 202.

        :return: An HTTP 202 response, once the notification is processed or safely ignored.
        :raise Forbidden: If the notification's authentication fails.
        """
        body = request.httprequest.get_data()
        try:
            data = json.loads(body)
        except ValueError:
            _logger.warning("Received a notification with an invalid JSON body.")
            raise Forbidden()
        _logger.info("Notification received from SHKeeper with data:\n%s", pprint.pformat(data))

        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('shkeeper', data)
        if not tx_sudo:
            # Acknowledge it so SHKeeper stops retrying a notification no transaction matches.
            return request.make_response('', status=202)

        self._verify_notification_origin(tx_sudo.provider_id, body)
        tx_sudo._process('shkeeper', data)
        return request.make_response('', status=202)

    @staticmethod
    def _verify_notification_origin(provider_sudo, body):
        """ Check the API key and the HMAC signature of the notification.

        :param payment.provider provider_sudo: The provider of the matching transaction.
        :param bytes body: The raw request body, as signed by SHKeeper.
        :return: None
        :raise Forbidden: If the API key or the signature is missing, invalid or expired.
        """
        secret = provider_sudo.shkeeper_api_key or ''
        headers = request.httprequest.headers
        api_key = headers.get(const.API_KEY_HEADER, '')
        signature = headers.get(const.WEBHOOK_SIGNATURE_HEADER, '').strip().lower()
        timestamp = headers.get(const.WEBHOOK_TIMESTAMP_HEADER, '')

        if not secret or not hmac.compare_digest(api_key, secret):
            _logger.warning("Received a notification with an invalid API key.")
            raise Forbidden()
        try:
            timestamp = int(timestamp)
        except ValueError:
            _logger.warning("Received a notification without a valid timestamp.")
            raise Forbidden()
        if abs(time.time() - timestamp) > const.WEBHOOK_MAX_AGE:
            _logger.warning("Received an expired notification.")
            raise Forbidden()
        expected = hmac.new(
            secret.encode(), f'{timestamp}.'.encode() + body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            _logger.warning("Received a notification with an invalid signature.")
            raise Forbidden()
