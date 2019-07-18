# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'EDI Integration for Agora',
    'version': '1.1',
    'summary': '',
    'category': 'Tools',
    'description': """
EDI Integration for Agora
=========================
    """,
    'depends': [
        'edi_ftp_connection',
        'sale_management',
        'stock'
    ],
    'data': [
        'data/partners.xml',
        'data/integrations.xml',
        # 'views/product_template.xml',
        'views/product_product.xml',
        'views/stock.xml',
    ],
    'hidden': True,
    'auto_install': False
}
