from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.payment_shkeeper import const


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('shkeeper', "SHKeeper")], ondelete={'shkeeper': 'set default'}
    )
    shkeeper_api_url = fields.Char(
        string="SHKeeper URL",
        help="The base URL of the SHKeeper instance, e.g. https://shkeeper.example.com.",
        required_if_provider='shkeeper',
    )
    shkeeper_api_key = fields.Char(
        string="API Key",
        help="The merchant API key from SHKeeper. It also signs the payment notifications.",
        required_if_provider='shkeeper',
        groups='base.group_system',
        copy=False,
    )
    shkeeper_callback_base_url = fields.Char(
        string="Callback Base URL",
        help="The URL at which SHKeeper reaches this Odoo instance. Leave empty to use the"
             " web.base.url system parameter.",
    )

    # === BUSINESS METHODS === #

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        self.ensure_one()
        if self.code != 'shkeeper':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _get_reset_values(self):
        """ Override of `payment` to supply the credential fields to reset. """
        if self.code != 'shkeeper':
            return super()._get_reset_values()
        return {'shkeeper_api_key': None}

    def _shkeeper_get_callback_url(self):
        """ Return the URL to which SHKeeper sends payment notifications. """
        self.ensure_one()
        base_url = self.shkeeper_callback_base_url or self.get_base_url()
        return f"{base_url.rstrip('/')}/payment/shkeeper/webhook"

    # === ACTION METHODS === #

    def action_shkeeper_test_connection(self):
        """ Check the credentials and list the cryptos that SHKeeper can accept. """
        self.ensure_one()
        data = self._send_api_request('GET', '/crypto')
        cryptos = data.get('crypto') or []
        configured = self.with_context(active_test=False).payment_method_ids.filtered(
            'shkeeper_crypto'
        ).mapped('shkeeper_crypto')
        missing = sorted(set(configured) - set(cryptos))
        message = _("SHKeeper accepts: %(cryptos)s.", cryptos=", ".join(cryptos) or _("nothing"))
        if missing:
            message += " " + _(
                "Not available in SHKeeper: %(missing)s.", missing=", ".join(missing)
            )
        raise UserError(message)

    # === REQUEST HELPERS === #

    def _build_request_url(self, endpoint, **kwargs):
        """ Override of `payment` to build the request URL. """
        if self.code != 'shkeeper':
            return super()._build_request_url(endpoint, **kwargs)
        return f"{self.shkeeper_api_url.rstrip('/')}/api/v1{endpoint}"

    def _build_request_headers(self, method, endpoint, payload, **kwargs):
        """ Override of `payment` to build the request headers. """
        if self.code != 'shkeeper':
            return super()._build_request_headers(method, endpoint, payload, **kwargs)
        return {const.API_KEY_HEADER: self.sudo().shkeeper_api_key}

    def _parse_response_error(self, response):
        """ Override of `payment` to parse the error message. """
        if self.code != 'shkeeper':
            return super()._parse_response_error(response)
        try:
            return response.json().get('message') or response.text
        except ValueError:
            return response.text
