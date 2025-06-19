# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import ValidationError

# Use user's requested import block for translate library
try:
    from translate import Translator
except ImportError:
    # This will stop Odoo from loading if the library is missing
    raise ImportError(
        'This module needs translate to automatically write word in arabic. '
        'Please install translate on your system. (sudo pip3 install translate)')

import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ths_partner_type_id = fields.Many2one(
        'ths.partner.type', string='Partner Type', required=True, index=True, tracking=True,
        default=lambda self: self.env.ref('ths_base.partner_type_contact', raise_if_not_found=False)
    )
    # Added Arabic Name field
    name_ar = fields.Char("Name (Arabic)", store=True, copy=True)

    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string='Gender')

    ths_gov_id = fields.Char(string='ID Number', help="National Identifier (ID)", readonly=False, copy=False, store=True)
    ths_dob = fields.Date(string='Date of Birth')
    ths_age = fields.Char(string='Age', compute='_compute_ths_age', store=False)

    # --- Onchange Methods ---
    @api.onchange('name')
    def onchange_name_translate(self):
        """Translates the English name to Arabic on change."""
        # Translator is guaranteed to be imported due to raise ImportError above
        if self.name:
            try:
                translator = Translator(to_lang="ar")
                self.name_ar = translator.translate(self.name)
            except Exception as e:
                # Log error but don't crash UI
                _logger.error(f"Failed to translate name '{self.name}' to Arabic: {e}")
                # Optionally display a user warning via return value if needed in v18+ onchanges
                # return {'warning': {'title': _("Translation Error"), 'message': _("Could not translate name to Arabic.")}}
        else:
            self.name_ar = False

    @api.onchange('ths_partner_type_id')
    def _onchange_ths_partner_type_id(self):
        """ Update standard company_type based on the partner type flags. """
        if self.ths_partner_type_id:
            self.company_type = 'company' if self.ths_partner_type_id.is_company else 'person'
        else:
            self.company_type = 'person'

    # @api.constrains('ths_gov_id')
    # def _check_id_numeric(self):
    #     for rec in self:
    #         if rec.ths_gov_id and not rec.ths_gov_id.isdigit():
    #             raise ValidationError(_("ID Number must contain only digits."))

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

    # --- Helper to get HR Handled Type IDs ---
    @api.model
    def _get_hr_handled_partner_type_ids(self):
        """ Safely gets the database IDs for partner types managed by ths_hr. """
        hr_handled_type_ids = []
        # Check if ths_hr module is installed before trying to access its data
        module_ths_hr = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'ths_hr'), ('state', '=', 'installed')], limit=1)
        if module_ths_hr:
            hr_handled_type_xmlids = [
                'ths_hr.partner_type_employee',
                'ths_hr.partner_type_part_time_employee',
                'ths_hr.partner_type_external_employee',
            ]
            for xmlid in hr_handled_type_xmlids:
                hr_type_record = self.env.ref(xmlid, raise_if_not_found=False)
                if hr_type_record:
                    hr_handled_type_ids.append(hr_type_record.id)
        return hr_handled_type_ids

    # --- Override Create Method ---
    @api.model_create_multi
    def create(self, vals_list):
        """ Override create to set company_type and generate Internal Reference based on Partner Type sequence,
            skipping ref generation for HR Employee types handled by ths_hr.
        """
        hr_handled_type_ids = self._get_hr_handled_partner_type_ids()

        # Pre-process vals to set company_type
        for vals in vals_list:
            if vals.get('ths_partner_type_id'):
                partner_type = self.env['ths.partner.type'].browse(vals['ths_partner_type_id']).exists()
                if partner_type:
                    expected_company_type = 'company' if partner_type.is_company else 'person'
                    if 'company_type' not in vals or vals.get('company_type') != expected_company_type:
                        vals['company_type'] = expected_company_type

        partners = super(ResPartner, self).create(vals_list)

        # Generate references only for non-HR handled types
        partners_to_ref = self.env['res.partner']
        for partner in partners:
            partner_type_id = partner.ths_partner_type_id.id if partner.ths_partner_type_id else None
            if partner_type_id and partner_type_id not in hr_handled_type_ids:
                partners_to_ref |= partner
            elif partner_type_id and partner_type_id in hr_handled_type_ids:
                _logger.debug(
                    f"THS_BASE: Skipping ref generation for partner '{partner.name}' (ID: {partner.id}) - Type handled by ths_hr.")

        # Generate references for the filtered partners IF ref is not already set
        for partner in partners_to_ref.sudo():
            if partner.ths_partner_type_id.sequence_id and not partner.ref:
                original_vals = next((v for v in vals_list if self._match_vals_to_partner(v, partner)), {})
                if 'ref' not in original_vals:
                    sequence = partner.ths_partner_type_id.sequence_id
                    try:
                        new_ref = sequence.next_by_id()
                        partner.write({'ref': new_ref})
                        _logger.info(
                            f"THS_BASE: Generated ref '{new_ref}' for partner '{partner.name}' (ID: {partner.id}) using sequence '{sequence.name}'.")
                    except Exception as e:
                        _logger.error(
                            f"THS_BASE: Failed ref generation for partner '{partner.name}' (ID: {partner.id}), sequence '{sequence.name}': {e}")

        return partners.with_env(self.env)

    # --- Override Write Method ---
    def write(self, vals):
        """ Override write to potentially generate ref if type changes, skipping HR types. """
        original_types = {}
        if 'ths_partner_type_id' in vals:
            original_types = {p.id: p.ths_partner_type_id.id for p in self}

        res = super().write(vals)

        if 'ths_partner_type_id' in vals:
            hr_handled_type_ids = self._get_hr_handled_partner_type_ids()
            # Filter partners where type changed, ref is empty, sequence exists, and new type is NOT HR handled
            partners_to_ref = self.filtered(
                lambda p: not p.ref and \
                          p.ths_partner_type_id and \
                          p.ths_partner_type_id.sequence_id and \
                          p.ths_partner_type_id.id != original_types.get(p.id) and \
                          p.ths_partner_type_id.id not in hr_handled_type_ids
            )
            for partner in partners_to_ref.sudo():
                try:
                    sequence = partner.ths_partner_type_id.sequence_id
                    new_ref = sequence.next_by_id()
                    partner.write({'ref': new_ref})
                    _logger.info(f"THS_BASE: Generated ref '{new_ref}' for partner {partner.id} on type change.")
                except Exception as e:
                    _logger.error(f"THS_BASE: Failed ref generation on type change for partner {partner.id}: {e}")
        return res

    # --- Helper Methods ---
    @staticmethod
    def _match_vals_to_partner(vals, partner):
        """ Helper to match vals dictionary to a created partner record. """
        if vals.get('name') and partner.name and partner.name == vals.get('name'):
            if 'email' in vals or 'vat' in vals:
                if vals.get('email') and partner.email and partner.email == vals.get('email'): return True
                if vals.get('vat') and partner.vat and partner.vat == vals.get('vat'): return True
                return False
            else:
                return True
        return False

    # --- Name Search Override ---
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        """ Override name_search to include ref, mobile, phone, ths_gov_id, and name_ar. """
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain_fields = ['name', 'ref', 'mobile', 'phone', 'name_ar', 'email', 'ths_gov_id']

            domain = expression.OR([[(field, operator, name)] for field in domain_fields])

        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid, order=order)
