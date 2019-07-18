# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import csv
import logging

from datetime import datetime as dt
from io import StringIO

from odoo import models, _

_logger = logging.getLogger(__name__)

CSV_HEADER = ['price', 'quantity', 'sku']


class ProductIntegration(models.Model):

    _inherit = 'edi.integration'

    def _get_out_synchronizations(self):
        """
        """

        agora_integration = self.env.ref('edi_agora.agora_products_integration')
        if self == agora_integration:

            now = dt.utcnow().strftime('%s')

            products = self.env['product.product'].with_context(
                pricelist=self.env.ref('edi_agora.agora_pricelist').id
            ).search([
                ('agora_sync', '=', True)
            ])

            output = StringIO()
            writer = csv.writer(output, delimiter=';')

            writer.writerow(CSV_HEADER)

            # location_id = self.env.ref('stock.stock_location_stock').id
            locations = self.env['stock.location'].search([('agora_sync', '=', True)])

            for p in products:
                if not p.default_code:
                    _logger.info(_('Product \'%s: %s\' skipped, no default code set') % (p.display_name, p.id))
                    continue

                # stock_quant = self.env['stock.quant'].search([('location_id', '=', location_id), ('product_id', '=', p.id)])
                stock_quant = self.env['stock.quant'].search([('location_id', 'in', locations.ids), ('product_id', '=', p.id)])
                qty = sum(stock_quant.mapped('quantity')) - sum(stock_quant.mapped('reserved_quantity'))

                if qty >= 0:
                    row = ['%.2f' % p.price, qty, p.default_code]
                    writer.writerow(row)

            content = output.getvalue()

            self.env['edi.synchronization'].create({
                'name': 'stock_%s.csv' % now,
                'filename': 'stock.csv',
                'integration_id': self.id,
                'content': content
            })

        return super(ProductIntegration, self)._get_out_synchronizations()