# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === Fields for Pet Type ===
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        index=True,
        help="The owner responsible for this pet.",
        tracking=True,
    )
    ths_pet_ids = fields.One2many(
        'res.partner',
        'ths_pet_owner_id',  # Inverse field name
        string='Pets',
    )
    ths_pet_count = fields.Integer(compute='_compute_ths_pet_count', string="# Pets")

    is_pet = fields.Boolean(compute="_compute_type_flags", store=True)
    is_pet_owner = fields.Boolean(compute="_compute_type_flags", store=True)

    ths_species_id = fields.Many2one('ths.species', string='Species', tracking=True)
    ths_breed_id = fields.Many2one('ths.breed', string='Breed', tracking=True)

    is_neutered_spayed = fields.Boolean(string="Neutered / Spayed")
    ths_microchip = fields.Char(string='Microchip Number', index=True)
    ths_deceased = fields.Boolean(string='Deceased', default=False, tracking=True)
    ths_deceased_date = fields.Date(string='Date of Death')

    @api.depends('ths_partner_type_id')
    def _compute_type_flags(self):
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)
        owner_type = self.env.ref('ths_medical_vet.partner_type_pet_owner', raise_if_not_found=False)
        for rec in self:
            rec.is_pet = rec.ths_partner_type_id.id == pet_type.id if pet_type else False
            rec.is_pet_owner = rec.ths_partner_type_id.id == owner_type.id if owner_type else False

    @api.depends('ths_pet_ids')
    def _compute_ths_pet_count(self):
        # Note: This might be inefficient if called on many partners at once.
        # Consider using a read_group instead if performance becomes an issue.
        for partner in self:
            partner.ths_pet_count = len(partner.ths_pet_ids)  # Simple count

    # === Constraints ===
    @api.constrains('ths_partner_type_id', 'ths_pet_owner_id')
    def _check_pet_has_owner(self):
        """
        Constraint to ensure an active Pet has an Owner.
        TODO: Decide on the final desired behavior for this constraint.
              Currently allows creation without an owner, but an active pet should have one.
        """
        pet_type_ref = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)
        if not pet_type_ref:
            _logger.warning(
                "Pet type XML ID 'ths_medical_vet.partner_type_pet' not found. Skipping _check_pet_has_owner constraint.")

        for partner in self:
            if partner.active and partner.ths_partner_type_id == pet_type_ref and not partner.ths_pet_owner_id:
                # Raise error only if it's an existing record being saved as active pet without owner,
                # or if you want to enforce it strictly always.
                # For now, to ensure creation is possible and then it can be enforced on active records:
                if partner.id:  # Only for existing records or make it a warning
                    _logger.warning(
                        f"Pet '{partner.name}' (ID: {partner.id}) is active and of type 'Pet' but has no Pet Owner assigned.")
                # To make it a hard stop for existing active pets:
                # raise ValidationError(_("An active partner of type 'Pet' must have a Pet Owner assigned."))
        return True  # Explicitly return True if no issues

    @api.constrains('ths_partner_type_id', 'parent_id', 'ths_pet_owner_id')
    def _check_owner_parent_consistency(self):
        """ Ensure Owner matches parent if parent is Owner type """
        owner_type = self.env.ref('ths_medical_vet.partner_type_pet_owner', raise_if_not_found=False)
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)
        if not owner_type or not pet_type: return

        for partner in self:
            if partner.ths_partner_type_id == pet_type:
                # Check if owner is set
                if partner.ths_pet_owner_id:
                    # If parent_id is also set and is an Owner, they should match the ths_pet_owner_id
                    if partner.parent_id and partner.parent_id.ths_partner_type_id == owner_type:
                        if partner.parent_id != partner.ths_pet_owner_id:
                            raise ValidationError(
                                _("If a Pet's parent contact is a Pet Owner, it must match the assigned Pet Owner field."))
                    # Also ensure owner itself is not a Pet
                    if partner.ths_pet_owner_id.ths_partner_type_id == pet_type:
                        raise ValidationError(_("A Pet's Owner cannot be another Pet."))

    # === Name Get (Optional enhancement) ===
    # def name_get(self):
    #     """ Enhance display name for Pets to show Owner """
    #     res = []
    #     pet_type_id = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False).id
    #     for partner in self:
    #         name = partner.name
    #         if pet_type_id and partner.ths_partner_type_id.id == pet_type_id and partner.ths_pet_owner_id:
    #             name = f"{partner.name} ({partner.ths_pet_owner_id.name})"
    #         res.append((partner.id, name))
    #     # Handle partners not processed (fall back to super) - This logic needs care
    #     remaining_ids = set(self.ids) - set(p[0] for p in res)
    #     if remaining_ids:
    #          res.extend(super(ResPartner, self.browse(list(remaining_ids))).name_get())
    #     # Re-sort results to original order? Or trust Odoo to handle it?
    #     return res

    # === Onchange (Set parent_id based on owner) ===
    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_id_set_parent(self):
        """ When owner is selected for a Pet, suggest setting parent_id for address """
        pet_type_xml_id = 'ths_medical_vet.partner_type_pet'
        pet_type = self.env.ref(pet_type_xml_id, raise_if_not_found=False)

        if not pet_type:
            _logger.warning(
                f"Partner type with XML ID '{pet_type_xml_id}' not found. Cannot execute onchange logic for setting parent based on pet owner.")
            return

        if self.ths_partner_type_id == pet_type and self.ths_pet_owner_id:
            if not self.parent_id or self.parent_id != self.ths_pet_owner_id:
                self.parent_id = self.ths_pet_owner_id
                # Address sync from parent should happen via standard Odoo's _onchange_parent_id()
                # which is typically triggered when parent_id changes.
                # If it's not triggering or you need more specific sync:
                # if self.parent_id:
                # This will trigger Odoo's logic to copy address from parent
                # It's better than manually copying fields as it respects `address_get` complexities.
                # self.update(self.env['res.partner']._get_inverse_address_fields(self.parent_id, False, False))

    # Action for the Pet Owner's "Pets" smart button
    def action_view_partner_pets(self):
        """Action to view pets linked to this Pet Owner."""
        self.ensure_one()
        pet_owner_type = self.env.ref('ths_medical_vet.partner_type_pet_owner', raise_if_not_found=False)
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)

        if not pet_owner_type or not pet_type:
            _logger.warning("Pet Owner or Pet type XML ID not found. Cannot open pets view.")
            return {}

        if self.ths_partner_type_id != pet_owner_type:
            return {}  # Should not be called if button visibility is correct

        return {
            'name': _('Pets of %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'list,form,kanban',
            'domain': [('ths_pet_owner_id', '=', self.id), ('ths_partner_type_id', '=', pet_type.id)],
            'context': {
                'default_ths_pet_owner_id': self.id,
                'default_ths_partner_type_id': pet_type.id,
                'default_parent_id': self.id,  # Also default pet's parent to the owner
            }
        }

    # Show Pet Name as Pet Name [Owner Name] in views
    # In Odoo 18, res.partner uses complete_name instead of display_name for stored computation
    @api.depends('name', 'is_pet', 'ths_pet_owner_id', 'ths_pet_owner_id.name')
    def _compute_display_name(self):
        """ Override display_name computation for pets - also updates complete_name for res.partner"""
        # Separate pets and non-pets to avoid recursion issues
        pets = self.filtered(lambda p: p.is_pet and p.ths_pet_owner_id)
        non_pets = self - pets

        # Process pets with custom formatting for BOTH display_name AND complete_name
        for partner in pets:
            base_name = partner.name or ''
            if '[' in base_name and base_name.endswith(']'):
                base_name = base_name.split(' [')[0]

            formatted_name = f"{base_name} [{partner.ths_pet_owner_id.name}]"

            # Update both fields for res.partner
            partner.display_name = formatted_name
            if hasattr(partner, 'complete_name'):
                partner.complete_name = formatted_name

        # Use standard Odoo computation for non-pets
        if non_pets:
            super(ResPartner, non_pets)._compute_display_name()

    def write(self, vals):
        """Override write to ensure both complete_name and display_name are recomputed"""
        result = super().write(vals)

        # Force recomputation when pet-related fields change
        if any(field in vals for field in ['name', 'ths_pet_owner_id', 'ths_partner_type_id']):
            # Clear the cache for both fields to force recomputation
            self.invalidate_recordset(['complete_name', 'display_name'])

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure proper computation for new pets"""
        records = super().create(vals_list)

        # Force computation for newly created pets
        pet_records = records.filtered(lambda r: r.is_pet and r.ths_pet_owner_id)
        if pet_records:
            pet_records.invalidate_recordset(['complete_name', 'display_name'])

        return records
