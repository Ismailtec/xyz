# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Pet-specific fields
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        index=True,
        help="The owner responsible for this pet.",
        tracking=True,
    )
    ths_pet_ids = fields.One2many(
        'res.partner',
        'ths_pet_owner_id',
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
        """Compute pet/owner flags based on partner type"""
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)
        owner_type = self.env.ref('ths_medical_vet.partner_type_pet_owner', raise_if_not_found=False)

        for rec in self:
            rec.is_pet = rec.ths_partner_type_id == pet_type if pet_type else False
            rec.is_pet_owner = rec.ths_partner_type_id == owner_type if owner_type else False

    @api.depends('ths_pet_ids')
    def _compute_ths_pet_count(self):
        """Count pets for each owner"""
        for partner in self:
            partner.ths_pet_count = len(partner.ths_pet_ids)

    @api.depends_context('company', 'show_pet_owner')
    @api.depends('name', 'is_pet', 'ths_pet_owner_id', 'ths_pet_owner_id.name')
    def _compute_display_name(self):
        """Optimized display name computation for pets with owner info"""
        # Separate pets and non-pets for efficient processing
        pets = self.filtered('is_pet')
        others = self - pets

        if pets:
            # Prefetch owner names to avoid N+1 queries
            pets.mapped('ths_pet_owner_id.name')

            # Check context for display preference
            show_owner = self.env.context.get('show_pet_owner', True)

            for pet in pets:
                base_name = pet.name or ''

                if show_owner and pet.ths_pet_owner_id:
                    # Remove any existing bracket info
                    if ' [' in base_name and base_name.endswith(']'):
                        base_name = base_name.split(' [')[0]

                    formatted = f"{base_name} [{pet.ths_pet_owner_id.name}]"
                    pet.display_name = formatted

                    # Update complete_name for res.partner in Odoo 18
                    if hasattr(pet, 'complete_name'):
                        pet.complete_name = formatted
                else:
                    pet.display_name = base_name
                    if hasattr(pet, 'complete_name'):
                        pet.complete_name = base_name

        # Let parent handle non-pets
        if others:
            super(ResPartner, others)._compute_display_name()

    # Constraints
    @api.constrains('ths_partner_type_id', 'ths_pet_owner_id', 'active')
    def _check_pet_has_owner(self):
        """Ensure active pets have owners"""
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)
        if not pet_type:
            return

        for partner in self:
            if (partner.active and
                    partner.ths_partner_type_id == pet_type and
                    not partner.ths_pet_owner_id and
                    partner.id):  # Only for existing records
                raise ValidationError(
                    _("Pet '%s' must have an owner assigned.", partner.name)
                )

    @api.constrains('ths_partner_type_id', 'parent_id', 'ths_pet_owner_id')
    def _check_owner_parent_consistency(self):
        """Ensure owner and parent consistency"""
        owner_type = self.env.ref('ths_medical_vet.partner_type_pet_owner', raise_if_not_found=False)
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)

        if not owner_type or not pet_type:
            return

        for partner in self:
            if partner.ths_partner_type_id == pet_type:
                # Check parent/owner consistency
                if (partner.parent_id and
                        partner.parent_id.ths_partner_type_id == owner_type and
                        partner.parent_id != partner.ths_pet_owner_id):
                    raise ValidationError(
                        _("Pet's parent contact must match the assigned Pet Owner.")
                    )

                # Ensure owner is not another pet
                if (partner.ths_pet_owner_id and
                        partner.ths_pet_owner_id.ths_partner_type_id == pet_type):
                    raise ValidationError(_("A Pet's Owner cannot be another Pet."))

    # Onchange methods
    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_id_set_parent(self):
        """Set parent_id when owner is selected"""
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)

        if pet_type and self.ths_partner_type_id == pet_type and self.ths_pet_owner_id:
            if not self.parent_id or self.parent_id != self.ths_pet_owner_id:
                self.parent_id = self.ths_pet_owner_id

    # Override create/write for cache invalidation
    def write(self, vals):
        """Override write to ensure proper display name recomputation"""
        # Check if pet-related fields are changing
        pet_fields = {'name', 'ths_pet_owner_id', 'ths_partner_type_id'}
        needs_recompute = bool(pet_fields & set(vals.keys()))

        result = super().write(vals)

        # Force recomputation when pet-related fields change
        if needs_recompute:
            self.invalidate_recordset(['complete_name', 'display_name'])

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure proper computation for new pets"""
        # Process vals to set parent_id from owner
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)

        for vals in vals_list:
            if (pet_type and
                    vals.get('ths_partner_type_id') == pet_type.id and
                    vals.get('ths_pet_owner_id') and
                    not vals.get('parent_id')):
                vals['parent_id'] = vals['ths_pet_owner_id']

        records = super().create(vals_list)

        # Force computation for newly created pets
        pet_records = records.filtered('is_pet')
        if pet_records:
            pet_records.invalidate_recordset(['complete_name', 'display_name'])

        return records

    # Actions
    def action_view_partner_pets(self):
        """Action to view pets linked to this Pet Owner"""
        self.ensure_one()

        if not self.is_pet_owner:
            return {}

        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)
        if not pet_type:
            return {}

        return {
            'name': _('Pets of %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'kanban,list,form',
            'domain': [('ths_pet_owner_id', '=', self.id)],
            'context': {
                'default_ths_pet_owner_id': self.id,
                'default_ths_partner_type_id': pet_type.id,
                'default_parent_id': self.id,
                'show_pet_owner': False,  # Don't show owner in pet list
            }
        }

    def action_view_medical_history(self):
        """View complete medical history for a pet"""
        self.ensure_one()

        if not self.is_pet:
            return {}

        return {
            'name': _('Medical History: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'ths.medical.base.encounter',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {
                'search_default_groupby_date': 1,
                'create': False,
            }
        }
