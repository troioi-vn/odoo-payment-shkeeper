{
    'name': "Payment Provider: SHKeeper",
    'version': '19.0.1.1.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "Accept crypto payments through a self-hosted SHKeeper gateway.",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'author': "troioi-vn",
    'website': "https://github.com/troioi-vn/odoo-payment-shkeeper",
    'depends': ['payment'],
    'data': [
        'views/payment_shkeeper_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_method_views.xml',

        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',  # Depends on `payment_method_data.xml`.
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
