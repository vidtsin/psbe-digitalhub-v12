from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    qty_available_stored = fields.Float(related='qty_available', store=True)
    virtual_available_stored = fields.Float(related='virtual_available', store=True)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    quant_count = fields.Integer(compute='_compute_quant_count', store=True)

    @api.depends('quant_ids')
    def _compute_quant_count(self):
        for rec in self:
            rec.quant_count = len(rec.quant_ids)
