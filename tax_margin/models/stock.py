# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockProductionLot(models.Model):

    _inherit = 'stock.production.lot'

    cost_price = fields.Float('Cost price')


class StockMoveLine(models.Model):

    _inherit = 'stock.move.line'

    def _action_done(self):
        """
        Assign the cost price (using the right currency), price_unit on purchase
        order line, to the lot in case the move line belongs to a tracked
        product by SN and we are in the context of a reception.
        """

        super(StockMoveLine, self)._action_done()

        def tracked_ml(ml):

            return (
                ml.exists() and     # Super method could delete some move lines
                ml.tracking == 'serial' and
                ml.move_id.picking_id.picking_type_code == 'incoming' and
                ml.move_id.purchase_line_id
            )

        for ml in self.filtered(tracked_ml):

            purchase_currency = ml.move_id.purchase_line_id.order_id.currency_id

            ml.lot_id.write({
                'cost_price': purchase_currency._convert(
                    ml.move_id.purchase_line_id.price_unit,
                    ml.move_id.company_id.currency_id,
                    ml.move_id.company_id,
                    fields.Date.today()
                )
            })
