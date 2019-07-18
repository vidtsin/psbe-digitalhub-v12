# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class Product(models.Model):

    _inherit = 'product.product'

    backmarket_sync = fields.Boolean(string='Synchronize with Back Market')
    backmarket_id = fields.Char('Back Market Identifier')
    backmarket_grade = fields.Integer(string='Grade for backmarket', default=0)

    @api.constrains('backmarket_sync', 'backmarket_id', 'backmarket_grade')
    def check_back_market_required(self):
        for product in self:
            if product.backmarket_sync and not product.backmarket_id:
                raise ValidationError(_("A Back Market identifier is required if the product needs to be synchronized."))
