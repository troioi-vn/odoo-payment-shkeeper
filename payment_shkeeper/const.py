# The codes of the payment methods to activate when SHKeeper is activated.
DEFAULT_PAYMENT_METHOD_CODES = {
    'shkeeper_btc',
    'shkeeper_usdt_trc20',
}

# SHKeeper invoice statuses, as sent in the `status` key of payment notifications.
STATUS_MAPPING = {
    'done': ('PAID', 'OVERPAID'),
    'pending': ('PARTIAL', 'UNPAID'),
}

# The maximum age, in seconds, of a signed payment notification. Matches SHKeeper's own check.
WEBHOOK_MAX_AGE = 300

WEBHOOK_SIGNATURE_HEADER = 'X-Shkeeper-Signature'
WEBHOOK_TIMESTAMP_HEADER = 'X-Shkeeper-Timestamp'
API_KEY_HEADER = 'X-Shkeeper-Api-Key'
