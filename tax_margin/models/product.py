# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, exceptions, fields, models, _


class product(models.Model):
    _inherit = 'product.product'

    att_regime_TVA = fields.Char('Régime de TVA', compute='_get_attributes', store=True)
    att_grade = fields.Char('Grade', compute='_get_attributes', store=True)
    att_color = fields.Char('Couleur', compute='_get_attributes', store=True)
    att_capacite_stockage = fields.Char('Capacité de stockage', compute='_get_attributes', store=True)
    att_pack = fields.Char('Pack', compute='_get_attributes', store=True)

    @api.multi
    @api.depends('attribute_value_ids', 'attribute_value_ids.name')
    def _get_attributes(self):
        for product in self:
            product.att_color = product.attribute_value_ids.filtered(
                lambda s: s.attribute_id.name == 'Couleur' if s.attribute_id else False
            ).name

            product.att_regime_TVA = product.attribute_value_ids.filtered(
                lambda s: s.attribute_id.name == 'Régime de TVA' if s.attribute_id else False
            ).name

            product.att_grade = product.attribute_value_ids.filtered(
                lambda s: s.attribute_id.name == 'Grade' if s.attribute_id else False
            ).name

            product.att_capacite_stockage = product.attribute_value_ids.filtered(
                lambda s: s.attribute_id.name == 'Capacité de stockage' if s.attribute_id else False
            ).name

            product.att_pack = product.attribute_value_ids.filtered(
                lambda s: s.attribute_id.name == 'Pack' if s.attribute_id else False
            ).name
