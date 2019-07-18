# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.website_sale_delivery.controllers.main import WebsiteSaleDelivery


class DHubWebsiteSaleDelivery(WebsiteSaleDelivery):

    def _update_website_sale_delivery_return(self, order, **post):

        result = super(DHubWebsiteSaleDelivery, self)._update_website_sale_delivery_return(order, **post)

        if order and order.order_line and any(order.mapped('order_line.tax_id.on_margin')):
            result['new_amount_untaxed'] = self._format_amount(order.amount_total, order.currency_id)

        return result
