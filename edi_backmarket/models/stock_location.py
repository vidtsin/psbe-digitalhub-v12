# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class Location(models.Model):

    _inherit = "stock.location"

    backmarket_sync = fields.Boolean(string='Synchronize with Backmarket')

    @api.constrains('code')
    def _agora_sync_constrains(self):
        if self.backmarket_sync and self.usage != 'internal':
            raise ValidationError(_('The location %s must be internal in order to synchronize it' % self.name))

