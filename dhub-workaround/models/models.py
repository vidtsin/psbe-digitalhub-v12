from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    qty_available_stored = fields.Float(compute='_compute_qty_available_stored', store=True)

    @api.depends('qty_available')
    def _compute_qty_available_stored(self):
        for rec in self:
            rec.qty_available_stored = rec.qty_available


class StockLocation(models.Model):
    _inherit = 'stock.location'

    quant_count = fields.Integer(compute='_compute_quant_count', store=True)

    @api.depends('quant_ids')
    def _compute_quant_count(self):
        for rec in self:
            rec.quant_count = len(rec.quant_ids)
