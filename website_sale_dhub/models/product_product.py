# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.http import request

from odoo.tools import float_compare, pycompat


class Product(models.Model):

    _inherit = 'product.product'

    @api.model
    def _update_website_publish_cron(self):
        self.with_context(prefetch_fields=False).search([
            ('type', '=', 'product')
        ]).update_website_publish()

    @api.multi
    def update_website_publish(self):
        location = self.env.ref('stock.stock_location_stock')

        products_to_unpublish = self.env['product.product']
        products_to_publish = self.env['product.product']

        for product in self:

            stock_quant = self.env['stock.quant'].search([
                ('location_id', '=', location.id),
                ('product_id', '=', product.id)
            ])

            qty = sum(stock_quant.mapped('quantity')) - sum(stock_quant.mapped('reserved_quantity'))

            if qty > 0:
                products_to_publish |= product
            else:
                products_to_unpublish |= product

        products_to_unpublish.write({
            'website_published': False
        })
        products_to_publish.write({
            'website_published': True
        })

    # # Copy/paste from original method
    def _website_price(self):

        qty = self._context.get('quantity', 1.0)
        partner = self.env.user.partner_id
        current_website = self.env['website'].get_current_website()
        pricelist = current_website.get_current_pricelist()
        company_id = current_website.company_id

        context = dict(self._context, pricelist=pricelist.id, partner=partner)
        self2 = self.with_context(context) if self._context != context else self

        for p, p2 in pycompat.izip(self, self2):

            has_margin = any(p.sudo().taxes_id.filtered('on_margin'))
            is_public = self.env.user == request.website.user_id
            show_total_included = bool(is_public or (has_margin and not is_public))

            ret = 'total_included' if show_total_included else 'total_excluded'

            taxes = partner.property_account_position_id.map_tax(p.sudo().taxes_id.filtered(lambda x: x.company_id == company_id))

            taxes_website_price = taxes.compute_all(p2.price, pricelist.currency_id, quantity=qty, product=p2, partner=partner)
            p.website_price = taxes_website_price[ret]

            # We must convert the price_without_pricelist in the same currency than the
            # website_price, otherwise the comparison doesn't make sense. Moreover, we show a price
            # difference only if the website price is lower
            price_without_pricelist = p.list_price
            if company_id.currency_id != pricelist.currency_id:
                price_without_pricelist = company_id.currency_id._convert(price_without_pricelist, pricelist.currency_id)

            taxes_price_without_pricelist = taxes.compute_all(price_without_pricelist, pricelist.currency_id)
            price_without_pricelist = taxes_price_without_pricelist[ret]

            p.website_price_difference = True if float_compare(price_without_pricelist, p.website_price, precision_rounding=pricelist.currency_id.rounding) > 0 else False

            taxes_website_public_price = taxes.compute_all(p2.lst_price, quantity=qty, product=p2, partner=partner)
            p.website_public_price = taxes_website_public_price[ret]
