# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, fields, models, _
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
import time


class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    is_margin = fields.Boolean('Is on margin', compute='_get_is_margin')

    @api.depends('invoice_line_ids')
    def _get_is_margin(self):
        for invoice in self:
            if self.env.ref('tax_margin.tax_margin_0').id in invoice.mapped('invoice_line_ids.invoice_line_tax_ids').ids or any(invoice.mapped('invoice_line_ids.invoice_line_tax_ids.is_on_margin')):
                invoice.is_margin = True
            else:
                invoice.is_margin = False

    @api.multi
    def get_taxes_values(self):
        tax_grouped = {}
        for line in self.invoice_line_ids:
            price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            if any(line.invoice_line_tax_ids.mapped('is_on_margin')):
                margin = (line.price_unit * line.quantity) - line.real_cost
            else:
                margin = line.price_unit

            taxes = line.invoice_line_tax_ids._compute_all(price_unit, self.currency_id, line.quantity, line.product_id,
                                                           self.partner_id, margin)['taxes']
            for tax in taxes:
                val = self._prepare_tax_line_vals(line, tax)
                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
        return tax_grouped

    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            if not inv.date_due:
                inv.with_context(ctx).write({'date_due': inv.date_invoice})
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            # iml = inv.invoice_line_move_line_get()

            iml = []

            for move_line in inv.invoice_line_move_line_get():
                product = self.env['product.product'].browse(move_line.get('product_id'))

                invl = self.env['account.invoice.line'].browse(move_line.get('invl_id'))

                if any(invl.invoice_line_tax_ids.mapped('is_on_margin')):
                    margin = (invl.price_unit*invl.quantity) - invl.real_cost

                    split_move_line = dict(move_line)
                    split_move_line1 = dict(move_line)

                    tax_amount = 0.00
                    for tax in self.env['account.move.line'].resolve_2many_commands('tax_ids', split_move_line.get('tax_ids')):
                        tax_amount += tax.get('amount')

                    split_move_line['price'] = invl.real_cost
                    split_move_line['price_unit'] = invl.real_cost
                    split_move_line['tax_ids'] = [(4, self.env.ref('l10n_be.1_attn_VAT-OUT-00-L').id, None)]
                    iml.append(split_move_line)

                    split_move_line1['price'] = (margin / (1+(tax_amount/100)))
                    split_move_line1['price_unit'] = margin / (1+(tax_amount/100))

                    iml.append(split_move_line1)

                else:
                    iml.append(move_line)

            iml += inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)

            name = inv.name or '/'
            if inv.payment_term_id:
                totlines = \
                inv.with_context(ctx).payment_term_id.with_context(currency_id=company_currency.id).compute(total,
                                                                                                            inv.date_invoice)[
                    0]
                res_amount_currency = total_currency
                ctx['date'] = inv._get_currency_rate_date()
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'invoice_id': inv.id
                })
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)

            date = inv.date or inv.date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
        return True


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    real_cost = fields.Float('Total Cost', compute='_get_real_cost')
    compute_real_cost = fields.Float('Total Cost')
    invoice_type = fields.Selection([
                         ('out_invoice', 'Customer Invoice'),
                         ('in_invoice', 'Vendor Bill'),
                         ('out_refund', 'Customer Credit Note'),
                         ('in_refund', 'Vendor Credit Note'),
                     ], related='invoice_id.type')

    @api.multi
    @api.depends('compute_real_cost')
    def _get_real_cost(self):
        for inv_line in self:
            if not inv_line.compute_real_cost:
                inv_line.real_cost = sum(inv_line.mapped('sale_line_ids.real_cost'))
            else:
                inv_line.real_cost = inv_line.compute_real_cost

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        taxes = False
        margin = 0.00

        if self.invoice_line_tax_ids:
            # if 'Marge' in self.product_id.attribute_value_ids.mapped('name'):
            if any(self.invoice_line_tax_ids.mapped('is_on_margin')):
                if self.invoice_id.type == 'out_refund':
                    cost = self.compute_real_cost
                else:
                    cost = sum(self.sale_line_ids.mapped('move_ids.move_line_ids.lot_id.cost_price'))

                margin = (self.price_unit * self.quantity) - cost
            taxes = self.invoice_line_tax_ids._compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id, margin=margin)

        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
        self.price_total = taxes['total_included'] if taxes else self.price_subtotal
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.with_context(date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign

    @api.onchange('product_id', 'invoice_line_tax_ids', 'quantity', 'price_unit', 'discount')
    def _onchange_product_id_tax(self):
        margin = (self.quantity * self.price_unit) - self.real_cost

        if any(self.invoice_line_tax_ids.mapped('is_on_margin')) and margin <= 0.00:
            self.invoice_line_tax_ids = [(6, 0, [self.env.ref('tax_margin.tax_margin_0').id])]
            return {
                'warning': {
                    'title': _('Tax'),
                    'message': _('Attention votre tax a été modifié car vous n\'avez pas de marge sur cette ligne'),
                }
            }
