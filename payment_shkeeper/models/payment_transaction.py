from urllib.parse import urlencode

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.payment_shkeeper import const
from odoo.addons.payment_shkeeper.controllers.main import SHKeeperController


_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    shkeeper_crypto = fields.Char(string="SHKeeper Crypto", readonly=True)
    shkeeper_crypto_name = fields.Char(string="Crypto", readonly=True)
    shkeeper_address = fields.Char(string="Payment Address", readonly=True)
    shkeeper_amount_crypto = fields.Char(string="Amount in Crypto", readonly=True)
    shkeeper_exchange_rate = fields.Char(string="Exchange Rate", readonly=True)
    shkeeper_balance_crypto = fields.Char(string="Received in Crypto", readonly=True)

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to create the SHKeeper invoice and return the redirect values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the
                                       transaction.
        :return: The dict of provider-specific rendering values.
        :rtype: dict
        """
        if self.provider_code != 'shkeeper':
            return super()._get_specific_rendering_values(processing_values)

        crypto = self.payment_method_id.shkeeper_crypto
        if not crypto:
            self._set_error(_("This payment method is not linked to an SHKeeper crypto."))
            return {}

        payload = {
            'external_id': self.reference,
            'fiat': self.currency_id.name,
            'amount': str(self.amount),
            'callback_url': self.provider_id._shkeeper_get_callback_url(),
        }
        try:
            invoice = self._send_api_request('POST', f'/{crypto}/payment_request', json=payload)
        except ValidationError as error:
            self._set_error(str(error))
            return {}
        # SHKeeper reports errors with HTTP 200 and a status field.
        if invoice.get('status') != 'success' or not invoice.get('wallet'):
            self._set_error(_(
                "SHKeeper could not create the payment: %(message)s",
                message=invoice.get('message') or _("unknown error"),
            ))
            return {}

        self.write({
            'provider_reference': str(invoice.get('id') or ''),
            'shkeeper_crypto': crypto,
            'shkeeper_crypto_name': invoice.get('display_name') or crypto,
            'shkeeper_address': invoice['wallet'],
            'shkeeper_amount_crypto': invoice.get('amount'),
            'shkeeper_exchange_rate': invoice.get('exchange_rate'),
        })
        return {
            'api_url': SHKeeperController._return_url,
            'reference': self.reference,
        }

    def _shkeeper_get_payment_uri(self):
        """ Return the value to encode in the payment QR code.

        Bitcoin wallets understand BIP 21 URIs with the amount; other wallets get the bare address.

        Note: self.ensure_one()

        :return: The payment URI or address.
        :rtype: str
        """
        self.ensure_one()
        if self.shkeeper_crypto == 'BTC':
            return f'bitcoin:{self.shkeeper_address}?amount={self.shkeeper_amount_crypto}'
        return self.shkeeper_address

    def _shkeeper_get_qr_code_url(self):
        """ Return the URL of the QR code image of the payment URI.

        Note: self.ensure_one()

        :return: The relative URL of the QR code image.
        :rtype: str
        """
        self.ensure_one()
        query = urlencode({
            'barcode_type': 'QR',
            'value': self._shkeeper_get_payment_uri(),
            'width': 240,
            'height': 240,
        })
        return f'/report/barcode/?{query}'

    def _extract_reference(self, provider_code, payment_data):
        """ Override of `payment` to extract the reference from the payment data. """
        if provider_code != 'shkeeper':
            return super()._extract_reference(provider_code, payment_data)
        return payment_data.get('external_id') or payment_data.get('reference')

    def _extract_amount_data(self, payment_data):
        """ Override of `payment` to skip the generic amount validation.

        SHKeeper decides whether an invoice is paid, within its own tolerance, and reports the
        received fiat balance rather than the invoiced amount. The fiat currency is checked in
        `_apply_updates` instead.
        """
        if self.provider_code != 'shkeeper':
            return super()._extract_amount_data(payment_data)
        return None

    def _apply_updates(self, payment_data):
        """ Override of `payment` to update the transaction based on the payment data. """
        if self.provider_code != 'shkeeper':
            return super()._apply_updates(payment_data)

        # The customer returned from the payment form: the invoice is awaiting payment.
        if 'status' not in payment_data:
            if self.state == 'draft':
                self._set_pending()
            return

        fiat = payment_data.get('fiat')
        if fiat and fiat != self.currency_id.name:
            self._set_error(_(
                "The currency from SHKeeper (%(fiat)s) doesn't match the transaction currency.",
                fiat=fiat,
            ))
            return

        if payment_data.get('balance_crypto') is not None:
            self.shkeeper_balance_crypto = str(payment_data['balance_crypto'])

        status = payment_data.get('status')
        if status in const.STATUS_MAPPING['done'] and payment_data.get('paid'):
            self._set_done()
        elif status in const.STATUS_MAPPING['pending']:
            if status == 'PARTIAL':
                message = _(
                    "Partial payment received: %(received)s of %(amount)s %(crypto)s.",
                    received=payment_data.get('balance_crypto'),
                    amount=self.shkeeper_amount_crypto,
                    crypto=self.shkeeper_crypto,
                )
                self._set_pending(state_message=message, extra_allowed_states=('pending',))
            elif self.state == 'draft':
                self._set_pending()
        else:
            _logger.warning(
                "Ignored data with unknown status %s for transaction %s.", status, self.reference
            )
