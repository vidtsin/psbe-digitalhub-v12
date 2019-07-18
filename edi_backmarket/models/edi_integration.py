# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import csv
import logging

from datetime import datetime as dt
from io import StringIO

from odoo import models, _

_logger = logging.getLogger(__name__)

CSV_HEADER = 'backmarket_id sku state price quantity lang warranty_delay'.split(' ')


class ProductIntegration(models.Model):

    _inherit = 'edi.integration'

    def _get_out_synchronizations(self):
        """
        """

        integration = self.env.ref('edi_backmarket.backmarket_products_integration')
        if self == integration:

            # NOTE: Keep pricelist in context
            Product = self.env['product.product'].with_context(
                pricelist=self.env.ref('edi_backmarket.backmarket_pricelist').id
            )

            now = dt.utcnow().strftime('%s')

            products = Product.search([
                ('backmarket_sync', '=', True)
            ])
            if not products:
                _logger.info(_('No products configured to be synchronized with %s' % integration.name))
                return self.env['edi.synchronization']

            locations = self.env['stock.location'].search([
                ('backmarket_sync', '=', True)
            ])
            if not locations:
                _logger.info(_('No locations found to synchronize with %s' % integration.name))
                return self.env['edi.synchronization']

            output = StringIO()
            writer = csv.writer(output, delimiter=';')

            writer.writerow(CSV_HEADER)

            products_to_sync = Product
            product_qties = {}
            for p in products:

                stock_quant = self.env['stock.quant'].search([
                    ('location_id', 'in', locations.ids),
                    ('product_id', '=', p.id)
                ])
                qty = sum(stock_quant.mapped('quantity')) - sum(stock_quant.mapped('reserved_quantity'))

                if qty < 0:
                    _logger.info(_('Product \'%s: %s\' skipped, unavailable') % (p.display_name, p.id))
                    continue

                products_to_sync |= p
                product_qties[p.id] = qty

            if not products_to_sync:
                _logger.info(_('No products found to synchronize with %s' % integration.name))
                return self.env['edi.synchronization']

            for p in products_to_sync:
                row = [p.backmarket_id, p.default_code, p.backmarket_grade, '%.0f' % p.price, int(product_qties[p.id]), 'fr-fr', 6]
                writer.writerow(row)

            content = output.getvalue()

            self.env['edi.synchronization'].create({
                'name': 'backmarket_%s.csv' % now,
                'filename': 'Import_products_%s.csv' % now,
                'integration_id': self.id,
                'content': content
            })

        return super(ProductIntegration, self)._get_out_synchronizations()
