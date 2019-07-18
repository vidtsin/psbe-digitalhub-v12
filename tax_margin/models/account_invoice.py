# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from functools import partial

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    on_margin = fields.Boolean('Is on margin', compute='_compute_on_margin', store=True, oldname='is_margin')
    amount_by_group_wo_margin_tax = fields.Binary(
        compute='_amount_by_group_wo_margin_tax',
        string='Tax amount by group (wo on margin tax)'
    )

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount',
        'tax_line_ids.amount_rounding','currency_id', 'company_id',
        'date_invoice', 'type'
    )
    def _compute_amount(self):
        """
        """

        super(AccountInvoice, self)._compute_amount()

        self.amount_tax = sum(
            self.currency_id.round(line.amount_total)
            for line in self.tax_line_ids
            if not line.tax_id.on_margin
        )

        self.amount_total = self.amount_untaxed + self.amount_tax

    @api.depends('invoice_line_ids')
    def _compute_on_margin(self):
        for invoice in self:
            invoice.on_margin = bool(invoice.invoice_line_ids.filtered('invoice_line_tax_ids.on_margin'))

    def _amount_by_group_wo_margin_tax(self):
        """
        """

        for invoice in self:

            fmt = partial(
                formatLang,
                invoice.with_context(lang=invoice.partner_id.lang).env,
                currency_obj=invoice.currency_id or invoice.company_id.currency_id
            )

            res = {}
            for line in invoice.tax_line_ids:

                if line.tax_id.on_margin:
                    continue

                res.setdefault(line.tax_id.tax_group_id, {'base': 0.0, 'amount': 0.0})
                res[line.tax_id.tax_group_id]['amount'] += line.amount_total
                res[line.tax_id.tax_group_id]['base'] += line.base

            res = sorted(res.items(), key=lambda l: l[0].sequence)

            invoice.amount_by_group_wo_margin_tax =  [(
                r[0].name, r[1]['amount'], r[1]['base'],
                fmt(r[1]['amount']), fmt(r[1]['base']),
                len(res),
            ) for r in res]

    def _prepare_tax_line_vals(self, line, tax):

        values = super(AccountInvoice, self)._prepare_tax_line_vals(line, tax)
        if tax.get('on_margin'):
            values['on_margin'] = True

        return values

    @api.multi
    def get_taxes_values(self):
        """
        """

        on_margin_invoices = self.filtered('on_margin')
        result = super(AccountInvoice, self - on_margin_invoices).get_taxes_values()

        for line in on_margin_invoices.invoice_line_ids:

            if not line.invoice_id.account_id:
                continue

            round_curr = line.invoice_id.currency_id.round

            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            if not line.on_margin:
                taxes = line.invoice_line_tax_ids.compute_all(
                    price,
                    currency=line.invoice_id.currency_id,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=line.invoice_id.partner_id
                )['taxes']
            else:
                cost_price = line.invoice_id.company_id.currency_id._convert(
                    line.cost_price,
                    line.invoice_id.currency_id,
                    line.invoice_id.company_id,
                    line.invoice_id.date_invoice or fields.Date.today()
                )
                taxes = line.invoice_line_tax_ids.compute_all(
                    price,
                    currency=line.invoice_id.currency_id,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=line.invoice_id.partner_id,
                    margin=(price * line.quantity) - cost_price
                )['taxes']

            for tax in taxes:

                val = self._prepare_tax_line_vals(line, tax)
                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                if key not in result:
                    result[key] = val
                    result[key]['base'] = round_curr(val['base'])
                else:
                    result[key]['amount'] += val['amount']
                    result[key]['base'] += round_curr(val['base'])

        return result

    def _create_split_move_lines(self, ml, invoice_line):
        """
        """

        tax_amount = 0.00
        for tax in self.env['account.move.line'].resolve_2many_commands('tax_ids', ml.get('tax_ids')):
            tax_amount += tax.get('amount')

        split_ml1 = dict(ml)    # Purchase price in company currency converted to invoice currency
        split_ml2 = dict(ml)    # Base to compute VAT from margin, also using the converted cost price

        cost_price = self.company_id.currency_id._convert(
            invoice_line.cost_price,
            self.currency_id,
            self.company_id,
            self.date_invoice or fields.Date.today()
        )

        margin = (invoice_line.price_unit * invoice_line.quantity) - cost_price
        amount = margin - (margin / (1 + tax_amount / 100))

        split_ml1['price_unit'] = split_ml1['price'] = cost_price
        split_ml1['tax_ids'] = [(4, invoice_line.invoice_id.company_id.on_margin_sale_tax_id.id, None)]

        split_ml2.update({
            'price': margin - amount,
            'price_unit': margin - amount
        })

        return [split_ml1, split_ml2]

    @api.model
    def invoice_line_move_line_get(self):
        """
        """

        res = super(AccountInvoice, self).invoice_line_move_line_get()
        if not self.on_margin:
            return res

        result = []
        for ml in res:

            invoice_line = self.env['account.invoice.line'].browse(ml.get('invl_id'))

            if not invoice_line.on_margin:
                result.append(ml)
                continue

            splited_mls = self._create_split_move_lines(ml, invoice_line)
            result.extend(splited_mls)

        return result

    @api.multi
    def action_invoice_open(self):
        """
        """

        for invoice in self:
            if not invoice.on_margin:
                continue

            if not invoice.company_id.on_margin_sale_tax_id:
                raise UserError(_('The tax on margin has not been configured on the company that is issuing the invoice. Please go to "Company settings" and configure the tax on margin.'))

        return super(AccountInvoice, self).action_invoice_open()

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

                if any(invl.invoice_line_tax_ids.mapped('on_margin')):
                    margin = (invl.price_unit*invl.quantity) - invl.cost_price

                    split_move_line = dict(move_line)
                    split_move_line1 = dict(move_line)

                    tax_amount = 0.00
                    for tax in self.env['account.move.line'].resolve_2many_commands('tax_ids', split_move_line.get('tax_ids')):
                        tax_amount += tax.get('amount')

                    split_move_line['price'] = invl.cost_price
                    split_move_line['price_unit'] = invl.cost_price
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
                        amount_currency = company_currency.with_context(ctx)._convert(t[1], inv.currency_id, inv.company_id, inv.date_invoice or fields.Date.today())
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

    on_margin = fields.Boolean('Is on margin', compute='_compute_on_margin', store=True)
    cost_price = fields.Float('Total Cost', compute='_compute_cost_price', store=True, oldname='real_cost')
    compute_real_cost = fields.Float('Total Cost 1')    # TODO: probably not used anymore
    compute_cost_price = fields.Float('Total Cost 2')   # TODO: probably not used anymore
    invoice_type = fields.Selection(related='invoice_id.type')

    @api.depends('invoice_line_tax_ids')
    def _compute_on_margin(self):
        for line in self:
            line.on_margin = bool(line.invoice_line_tax_ids.filtered('on_margin'))

    @api.multi
    @api.depends('compute_cost_price', 'sale_line_ids.cost_price')
    def _compute_cost_price(self):
        for inv_line in self:
            if not inv_line.compute_cost_price:
                inv_line.cost_price = sum(inv_line.mapped('sale_line_ids.cost_price'))
            else:
                inv_line.cost_price = inv_line.compute_cost_price

    def _compute_price_on_margin(self):

        currency = self.invoice_id and self.invoice_id.currency_id or None
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        qty = self.quantity

        cost_price = self.invoice_id.company_id.currency_id._convert(
            self.cost_price,
            self.invoice_id.currency_id,
            currency,
            self.invoice_id.date_invoice or fields.Date.today()
        )

        taxes = self.invoice_line_tax_ids.compute_all(
            price,
            currency=currency,
            quantity=qty,
            product=self.product_id,
            partner=self.invoice_id.partner_id,
            margin=(price * qty) - cost_price
        )

        self.price_subtotal = price_subtotal_signed = taxes['total_excluded']
        self.price_total = taxes['total_included']
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            currency = self.invoice_id.currency_id
            date = self.invoice_id._get_currency_rate_date()
            price_subtotal_signed = currency._convert(
                price_subtotal_signed,
                self.invoice_id.company_id.currency_id,
                self.company_id or self.env.user.company_id,
                date or fields.Date.today()
            )

        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id',
        'invoice_id.company_id', 'invoice_id.date_invoice', 'invoice_id.date'
    )
    def _compute_price(self):
        """
        """

        if self.filtered('invoice_line_tax_ids.on_margin'):
            self._compute_price_on_margin()
        else:
            super(AccountInvoiceLine, self)._compute_price()

    @api.onchange('product_id', 'invoice_line_tax_ids', 'quantity', 'price_unit', 'discount')
    def _onchange_product_id_tax(self):
        margin = (self.quantity * self.price_unit) - self.cost_price

        if any(self.invoice_line_tax_ids.mapped('on_margin')) and margin <= 0.00:
            self.invoice_line_tax_ids = [(6, 0, [self.env.ref('tax_margin.tax_margin_0').id])]
            return {
                'warning': {
                    'title': _('Tax'),
                    'message': _('Attention votre tax a été modifié car vous n\'avez pas de marge sur cette ligne'),
                }
            }


class AccountInvoiceTax(models.Model):

    _inherit = "account.invoice.tax"

    on_margin = fields.Boolean('Is on margin', oldname='is_on_margin')
