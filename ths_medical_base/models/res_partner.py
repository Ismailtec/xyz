# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string='Gender')

    ths_dob = fields.Date(string='Date of Birth')
    ths_age = fields.Char(string='Age', compute='_compute_ths_age', store=False)

    # === Compute Methods ===
    @api.depends('ths_dob')
    def _compute_ths_age(self):
        for partner in self:
            age_str = ""
            if partner.ths_dob:
                today = fields.Date.context_today(partner)
                delta = today - partner.ths_dob
                years = delta.days // 365
                months = (delta.days % 365) // 30  # Approximate
                days = (delta.days % 365) % 30  # Approximate

                if years > 0:
                    age_str += f"{years}y "
                if months > 0:
                    age_str += f"{months}m "
                if years == 0 and months == 0 and days >= 0:  # Show days only if less than a month old
                    age_str += f"{days}d"
                age_str = age_str.strip()
            partner.ths_age = age_str or "N/A"