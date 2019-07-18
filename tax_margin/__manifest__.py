# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Tax on margin',
    'version': '2.0',
    'category': 'Accounting',
    'sequence': 35,
    'summary': 'Compute Tax on Margin',
    'description': """
        compute tax only on margin and not in unit price
        """,
    'depends': [
        'sale_management',
        'account_accountant',
        'purchase_stock',
        'sale_stock',
        'sale',
        'stock',
        'sale_management',
        'purchase',
        'l10n_be',
    ],
    'demo': [
        'demo/taxes.xml',
        'demo/products.xml'
    ],
    'data': [
        'data/account_taxes.xml',
        'views/account_invoice.xml',
        'views/account_tax.xml',
        'views/stock_production_lot.xml',
        'views/res_company.xml',
        'report/invoice.xml',
        'report/sale_order.xml',
    ],
    'test': [

    ],
}
