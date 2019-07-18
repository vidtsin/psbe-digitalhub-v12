# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Company(models.Model):

    _inherit = 'res.company'

    on_margin_sale_tax_id = fields.Many2one(comodel_name='account.tax', string='On margin sale tax', help='')
    available_tax_ids = fields.Many2many(comodel_name='account.tax', compute='_compute_available_taxes', string='Available on margin purchase taxes')

    def _compute_available_taxes(self):

        Tax = self.env['account.tax']
        for company in self:
            taxes = Tax.search([
                ('company_id', '=', company.id),
                ('type_tax_use', '=', 'sale')
            ])
            company.available_tax_ids = taxes
