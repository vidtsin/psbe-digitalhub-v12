# -*- coding: utf-8 -*-
{
    'name': "website_sale_dhub",
    'summary': "",
    'description': """
DHub's eCommerce Customizations
===============================
    """,
    'author': "Odoo SA",
    'website': "http://www.odoo.com",
    'category': 'Website',
    'version': '11.0.0.1',
    'depends': ['website_sale', 'stock', 'tax_margin'],
    'data': [
        'views/templates.xml',
        'data/update_website_publish_cron.xml'
    ],
    'auto_install': True
}
