# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'EDI Integration for Back Market',
    'version': '1.1',
    'summary': '',
    'category': 'Tools',
    'description': """
EDI Integration for BackMarket
==============================
    """,
    'depends': [
        'edi_ftp_connection',
        'stock',
        'tax_margin'
    ],
    'data': [
        'data/partners.xml',
        'data/integrations.xml',
        'views/product_product.xml',
        'views/stock_location.xml'
    ],
    'hidden': True,
    'auto_install': False
}
