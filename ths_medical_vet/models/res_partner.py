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
        help="The owner responsible for this pet and billing.",
        tracking=True,
        domain="[('ths_partner_type_id.name','=','Pet Owner')]",
        ondelete='restrict',  # Prevent deletion of owners who have pets
    )

    ths_pet_ids = fields.One2many(
        'res.partner',
        'ths_pet_owner_id',
        string='Pets',
        help="Pets owned by this Pet Owner."
    )

    ths_pet_count = fields.Integer(
        compute='_compute_ths_pet_count',
        string="# Pets",
        help="Number of pets owned by this Pet Owner."
    )

    # Computed boolean flags for UI logic
    is_pet = fields.Boolean(
        compute="_compute_type_flags",
        store=True,
        index=True,
        help="True if this partner is a Pet."
    )

    is_pet_owner = fields.Boolean(
        compute="_compute_type_flags",
        store=True,
        index=True,
        help="True if this partner is a Pet Owner."
    )

    # Pet-specific medical fields
    ths_species_id = fields.Many2one(
        'ths.species',
        string='Species',
        tracking=True,
        help="Species of the pet (Dog, Cat, etc.)"
    )

    ths_breed_id = fields.Many2one(
        'ths.breed',
        string='Breed',
        tracking=True,
        help="Specific breed of the pet."
    )

    # Pet health and identification fields
    is_neutered_spayed = fields.Boolean(
        string="Neutered / Spayed",
        help="Whether the pet has been neutered or spayed."
    )

    ths_microchip = fields.Char(
        string='Microchip Number',
        index=True,
        help="Unique microchip identification number."
    )

    ths_deceased = fields.Boolean(
        string='Deceased',
        default=False,
        tracking=True,
        help="Mark if the pet is deceased."
    )

    ths_deceased_date = fields.Date(
        string='Date of Death',
        help="Date when the pet passed away."
    )

    # Additional vet-specific fields
    ths_insurance_number = fields.Char(
        string='Pet Insurance Number',
        help="Pet insurance policy number if applicable."
    )

    ths_emergency_contact = fields.Many2one(
        'res.partner',
        string='Emergency Contact',
        help="Emergency contact person if pet owner is unavailable."
    )

    # --- COMPUTED METHODS ---

    @api.depends('ths_partner_type_id')
    def _compute_type_flags(self):
        """Compute pet/owner flags based on partner type"""
        # Use xml_id references for better reliability
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)
        owner_type = self.env.ref('ths_medical_vet.partner_type_pet_owner', raise_if_not_found=False)

        for rec in self:
            rec.is_pet = rec.ths_partner_type_id == pet_type if pet_type else False
            rec.is_pet_owner = rec.ths_partner_type_id == owner_type if owner_type else False

    @api.depends('ths_pet_ids')
    def _compute_ths_pet_count(self):
        """Count active pets for each owner"""
        for partner in self:
            if partner.is_pet_owner:
                # Count only active pets
                partner.ths_pet_count = len(partner.ths_pet_ids.filtered('active'))
            else:
                partner.ths_pet_count = 0

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
                    # Remove any existing bracket info to avoid duplication
                    if ' [' in base_name and base_name.endswith(']'):
                        base_name = base_name.split(' [')[0]

                    formatted = f"{base_name} [{pet.ths_pet_owner_id.name}]"
                    pet.display_name = formatted

                    # Update complete_name for compatibility
                    if hasattr(pet, 'complete_name'):
                        pet.complete_name = formatted
                else:
                    pet.display_name = base_name
                    if hasattr(pet, 'complete_name'):
                        pet.complete_name = base_name

        # Let parent handle non-pets
        if others:
            super(ResPartner, others)._compute_display_name()

    # --- CONSTRAINTS ---

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
                    partner.id):  # Only for existing records (not during creation)
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

    @api.constrains('ths_deceased', 'ths_deceased_date')
    def _check_deceased_date(self):
        """Validate deceased date logic"""
        for partner in self:
            if partner.ths_deceased and not partner.ths_deceased_date:
                # Auto-set deceased date to today if not provided
                partner.ths_deceased_date = fields.Date.today()
            elif not partner.ths_deceased and partner.ths_deceased_date:
                # Clear deceased date if pet is marked as alive
                partner.ths_deceased_date = False

    # --- ONCHANGE METHODS ---

    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_id_set_parent(self):
        """Set parent_id when owner is selected"""
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)

        if pet_type and self.ths_partner_type_id == pet_type and self.ths_pet_owner_id:
            if not self.parent_id or self.parent_id != self.ths_pet_owner_id:
                self.parent_id = self.ths_pet_owner_id

    @api.onchange('ths_species_id')
    def _onchange_species_clear_breed(self):
        """Clear breed when species changes"""
        if self.ths_species_id:
            # Clear breed to force user to select appropriate breed for new species
            self.ths_breed_id = False
            # TODO: Add domain filter for breeds based on selected species

    @api.onchange('ths_deceased')
    def _onchange_deceased_set_date(self):
        """Auto-set deceased date when marking as deceased"""
        if self.ths_deceased and not self.ths_deceased_date:
            self.ths_deceased_date = fields.Date.today()
        elif not self.ths_deceased:
            self.ths_deceased_date = False

    # --- OVERRIDE CREATE/WRITE ---

    def write(self, vals):
        """Override write to ensure proper display name recomputation and business logic"""
        # Check if pet-related fields are changing
        pet_fields = {'name', 'ths_pet_owner_id', 'ths_partner_type_id'}
        needs_recompute = bool(pet_fields & set(vals.keys()))

        # Handle deceased logic
        if 'ths_deceased' in vals:
            if vals['ths_deceased'] and 'ths_deceased_date' not in vals:
                vals['ths_deceased_date'] = fields.Date.today()
            elif not vals['ths_deceased']:
                vals['ths_deceased_date'] = False

        result = super().write(vals)

        # Force recomputation when pet-related fields change
        if needs_recompute:
            self.invalidate_recordset(['complete_name', 'display_name'])

        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure proper computation for new pets and business logic"""
        pet_type = self.env.ref('ths_medical_vet.partner_type_pet', raise_if_not_found=False)

        for vals in vals_list:
            # Set parent_id from owner for pets
            if (pet_type and
                    vals.get('ths_partner_type_id') == pet_type.id and
                    vals.get('ths_pet_owner_id') and
                    not vals.get('parent_id')):
                vals['parent_id'] = vals['ths_pet_owner_id']

            # Handle deceased logic during creation
            if vals.get('ths_deceased') and not vals.get('ths_deceased_date'):
                vals['ths_deceased_date'] = fields.Date.today()

        records = super().create(vals_list)

        # Force computation for newly created pets
        pet_records = records.filtered('is_pet')
        if pet_records:
            pet_records.invalidate_recordset(['complete_name', 'display_name'])

        return records

    # --- BUSINESS ACTIONS ---

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
                'create': True,  # Allow creating new pets
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
            'domain': [('patient_ids', 'in', [self.id])],  # Updated for Many2many
            'context': {
                'search_default_groupby_date': 1,
                'create': False,
            }
        }

    def action_view_appointments(self):
        """View appointments for this pet or pet owner"""
        self.ensure_one()

        if self.is_pet:
            # Show appointments where this pet is a patient
            domain = [('ths_patient_ids', 'in', [self.id])]
            name = _('Appointments for %s') % self.name
        elif self.is_pet_owner:
            # Show appointments where this person is the billing customer
            domain = [('partner_id', '=', self.id)]
            name = _('Appointments for %s') % self.name
        else:
            return {}

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'calendar,list,form',
            'domain': domain,
            'context': {
                'default_partner_id': self.id if self.is_pet_owner else False,
                'default_ths_pet_owner_id': self.id if self.is_pet_owner else self.ths_pet_owner_id.id,
                'default_ths_patient_ids': [(6, 0, [self.id])] if self.is_pet else False,
            }
        }

    # --- HELPER METHODS ---

    def _get_pet_age_in_years(self):
        """Calculate pet age in years and months"""
        self.ensure_one()
        if not self.is_pet or not self.ths_dob:
            return ''

        today = fields.Date.today()
        if self.ths_deceased and self.ths_deceased_date:
            end_date = self.ths_deceased_date
        else:
            end_date = today

        age_days = (end_date - self.ths_dob).days
        age_years = age_days // 365
        age_months = (age_days % 365) // 30

        if age_years > 0:
            return _('%d years, %d months') % (age_years, age_months)
        else:
            return _('%d months') % age_months

    def _get_vaccination_status(self):
        """Get vaccination status summary for pet"""
        # TODO: Implement when vaccination module is added
        self.ensure_one()
        if not self.is_pet:
            return ''
        return 'Vaccination status tracking - TODO'

    def _get_next_appointment(self):
        """Get next scheduled appointment for pet or owner"""
        self.ensure_one()

        if self.is_pet:
            domain = [('ths_patient_ids', 'in', [self.id])]
        elif self.is_pet_owner:
            domain = [('partner_id', '=', self.id)]
        else:
            return False

        domain.extend([
            ('start', '>=', fields.Datetime.now()),
            ('appointment_status', 'in', ['draft', 'confirmed'])
        ])

        return self.env['calendar.event'].search(domain, order='start asc', limit=1)

    # --- TODO: Future enhancements ---
    # TODO: Add integration with pet insurance systems
    # TODO: Add automatic reminders for vaccinations based on species/breed
    # TODO: Add integration with pet boarding system
    # TODO: Add pet photo management
    # TODO: Add emergency contact notification system
    # TODO: Add integration with pet registry/microchip database
