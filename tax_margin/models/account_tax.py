# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models


class AccountTax(models.Model):

    _inherit = 'account.tax'

    on_margin = fields.Boolean('Is on margin', oldname='is_on_margin')
    amount_type = fields.Selection(selection_add=[('margin', 'On Margin')])

    @api.onchange('on_margin')
    def onchange_on_margin(self):
        """
        Reset amount_type and price_include to their default values, 'percent'
        and False respectively.

        Set type_use_tax to 'sale' if on_margin otherwise force user selecting
        the desired value (required).

        Unset include_base_amount for taxes comupted on margin.
        """

        for tax in self:

            tax.amount_type = 'margin' if tax.on_margin else 'percent'
            tax.price_include = tax.on_margin
            tax.type_tax_use = 'sale' if tax.on_margin else 'none'

            if tax.on_margin:
                tax.include_base_amount = False

    def _compute_amount(self, base_amount, price_unit, quantity=1.0, product=None, partner=None):
        """
        Handle case for tax on margin
        """

        self.ensure_one()

        if self.amount_type != 'margin':
            return super(AccountTax, self)._compute_amount(
                base_amount,
                price_unit,
                quantity=quantity,
                product=product,
                partner=partner
            )

        return base_amount - (base_amount / (1 + self.amount / 100))

    @api.multi
    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, margin=0.0):
        """
        Handle case for tax on margin
        """

        non_margin_taxes = self.filtered(lambda t: not t.on_margin)

        result = super(AccountTax, non_margin_taxes).compute_all(
            price_unit,
            currency=currency,
            quantity=quantity,
            product=product,
            partner=partner
        )

        margin_taxes = self - non_margin_taxes
        if not margin_taxes:
            return result

        if len(self) == 0:
            company_id = self.env.user.company_id
        else:
            company_id = self[0].company_id

        if not currency:
            currency = company_id.currency_id

        prec = currency.decimal_places

        round_tax = False if company_id.tax_calculation_rounding_method == 'round_globally' else True
        if 'round' in self.env.context:
            round_tax = bool(self.env.context['round'])

        if not round_tax:
            prec += 5

        for tax in margin_taxes:

            tax_amount = tax._compute_amount(
                margin,
                price_unit,
                quantity=quantity,
                product=product,
                partner=partner
            )
            if not round_tax:
                tax_amount = round(tax_amount, prec)
            else:
                tax_amount = currency.round(tax_amount)

            result['taxes'].append({
                'id': tax.id,
                'name': tax.with_context(**{'lang': partner.lang} if partner else {}).name,
                'amount': tax_amount,
                'base': margin,
                'on_margin': True,
                'sequence': tax.sequence,
                'account_id': tax.account_id.id,
                'refund_account_id': tax.refund_account_id.id,
                'analytic': tax.analytic,
                'price_include': tax.price_include,
                'tax_exigibility': tax.tax_exigibility
            })

        return result
