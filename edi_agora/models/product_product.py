# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class Product(models.Model):

    _inherit = 'product.product'

    agora_sync = fields.Boolean(string='Synchronize with Agora')

    # @api.model
    # def create(self, values):
    #     """
    #     """

    #     product = super(Product, self).create(values)

    #     product.agora_sync = product.product_tmpl_id.agora_sync

    #     return product
