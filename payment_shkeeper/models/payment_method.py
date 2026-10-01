from odoo import fields, models


class PaymentMethod(models.Model):
    _inherit = 'payment.method'

    shkeeper_crypto = fields.Char(
        string="SHKeeper Crypto",
        help="The SHKeeper crypto name used for this payment method, as listed by the"
             " /api/v1/crypto endpoint of SHKeeper, e.g. BTC or USDT.",
    )
