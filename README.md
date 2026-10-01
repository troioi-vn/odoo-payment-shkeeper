# Odoo payment provider for SHKeeper

`payment_shkeeper` lets an Odoo 19 shop accept crypto payments through
[SHKeeper](https://github.com/vsys-host/shkeeper.io), a self-hosted,
non-custodial crypto payment gateway. Payments go straight to wallets you
control; no third party holds the funds or sees your customers.

It depends only on Odoo's `payment` module, so it serves website checkout and
portal payment links alike. It is tested on Odoo 19 Community with website
checkout.

## How a payment works

1. At checkout the customer picks a crypto payment method, for example Bitcoin
   or USDT (TRC20).
2. Odoo asks SHKeeper for an invoice in the order's currency. SHKeeper returns a
   fresh address and the amount in crypto.
3. The customer lands on Odoo's payment status page, which shows the address,
   the exact amount and a QR code. The transaction is *pending*.
4. Once the payment is confirmed on chain, SHKeeper sends a signed notification
   to Odoo. Odoo checks the signature and marks the transaction *done*, which
   confirms the order and sends the usual confirmation email.

Customers never talk to SHKeeper directly, so it can stay on a private network.
Only Odoo needs to reach SHKeeper's API, and SHKeeper needs to reach Odoo's
notification URL.

## Requirements

- Odoo 19.0
- A SHKeeper instance that signs its notifications with `X-Shkeeper-Signature`
  and `X-Shkeeper-Timestamp` (tested with SHKeeper 2.5.32)
- A merchant API key from SHKeeper
- Odoo's company currency, or the order currency, must be a fiat currency that
  SHKeeper can convert, such as USD or EUR

## Installation

Put the `payment_shkeeper` directory in a folder that is on Odoo's
`addons_path`, update the apps list, and install **Payment Provider: SHKeeper**.

## Configuration

1. Go to **Accounting / Website → Configuration → Payment Providers** and open
   **Crypto (SHKeeper)**.
2. On the **Credentials** tab, fill in:
   - **SHKeeper URL**: the base URL of your instance, without `/api/v1`
   - **API Key**: SHKeeper's merchant API key. It also verifies notifications.
   - **Callback Base URL** (optional): the address at which SHKeeper reaches
     Odoo. Leave it empty to use `web.base.url`. Set it when SHKeeper should use
     an internal hostname.
3. Click **Test Connection**. It lists the cryptos SHKeeper offers and warns
   about configured payment methods SHKeeper does not offer.
4. Set the state to **Enabled** and publish the provider.

### Payment methods

The module adds two payment methods: **Bitcoin** (`BTC`) and **USDT (TRC20)**
(`USDT`). Each payment method has an **SHKeeper Crypto** field holding the
crypto name SHKeeper uses in its API (`GET /api/v1/crypto`). To offer another
crypto that your SHKeeper supports, create a payment method with that name in
**SHKeeper Crypto** and add it to the provider.

## Security

- The notification URL is `/payment/shkeeper/webhook`. A notification is
  accepted only if its `X-Shkeeper-Api-Key` header matches the provider's API
  key and its HMAC-SHA256 signature over `"<timestamp>.<body>"` is valid. Odoo
  rejects notifications older than five minutes.
- The status SHKeeper reports, `PAID` or `OVERPAID`, decides whether a payment
  is complete. SHKeeper applies its own tolerance for small differences. Odoo
  still checks that the notification's fiat currency matches the transaction's.
- The browser return route, `/payment/shkeeper/return`, can only move a
  transaction from draft to pending. It never confirms a payment.

## Limitations

- Refunds are not supported. Send them from your wallet and record them in Odoo
  by hand.
- Each payment attempt gets its own SHKeeper invoice. If the customer pays after
  SHKeeper has recalculated the exchange rate, SHKeeper decides whether the
  amount still counts as paid.
- A partial payment leaves the transaction pending, and the status page shows
  how much has arrived. The customer can send the rest to the same address.
- If SHKeeper is down or its wallets are locked, Odoo shows the customer a
  payment error, and the order can be paid another way.

## Development

Run the tests on a throwaway database:

```sh
odoo -d shkeeper_test --addons-path=<odoo>/addons,<this repo> \
  -i payment_shkeeper --test-tags=/payment_shkeeper --stop-after-init
```

## License

LGPL-3.0, like Odoo's own payment providers. See [LICENSE](LICENSE).
