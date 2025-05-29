# -*- coding: utf-8 -*-

from odoo import models, fields


class ThsPendingPosItem(models.Model):
    _inherit = 'ths.pending.pos.item'  # Inherit from base pending POS item

    boarding_stay_id = fields.Many2one(
        'vet.boarding.stay',
        string='Source Boarding Stay',
        ondelete='cascade',
        index=True,
        copy=False
    )
