# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class ThsMedicalBaseEncounter(models.Model):
    _inherit = 'ths.medical.base.encounter'

    # Override patient_ids for vet context - now refers to pets
    patient_ids = fields.Many2many(
        'res.partner',
        'ths_medical_encounter_patient_rel',
        'encounter_id',
        'patient_id',
        string='Pets',  # Relabeled for veterinary context
        domain="[('ths_partner_type_id.name', '=', 'Pet')]",
        help="Pets receiving veterinary care in this encounter."
    )

    # Pet Owner field for vet billing context
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        compute='_compute_pet_owner',
        inverse='_inverse_pet_owner',
        domain="[('ths_partner_type_id.name','=','Pet Owner')]",
        store=True,
        readonly=False,
        index=True,
        tracking=True,
        help="Pet owner responsible for billing. This is synced with the encounter's billing customer.",
    )

    # Computed domain string for pets based on selected owner
    patient_ids_domain = fields.Char(
        compute='_compute_patient_domain',
        store=False
    )

    # Add related fields from Pet for convenience in encounter view/reports
    ths_species = fields.Many2one(
        'ths.species',
        string='Primary Pet Species',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True,
        help="Species of the primary pet in this encounter"
    )
    ths_breed = fields.Many2one(
        'ths.breed',
        string='Primary Pet Breed',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True,
        help="Breed of the primary pet in this encounter"
    )
    ths_pet_age = fields.Char(
        string='Primary Pet Age',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True,
        help="Age of the primary pet in this encounter"
    )
    ths_pet_gender = fields.Selection(
        selection=[('male', 'Male'), ('female', 'Female')],
        string='Primary Pet Gender',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True,
        help="Gender of the primary pet in this encounter"
    )

    # Count fields for multiple pets
    total_pets_count = fields.Integer(
        string='Total Pets',
        compute='_compute_pets_summary',
        store=False,
        readonly=True,
        help="Total number of pets in this encounter"
    )
    pets_summary = fields.Char(
        string='Pets Summary',
        compute='_compute_pets_summary',
        store=False,
        readonly=True,
        help="Summary of all pets in this encounter"
    )

    # Add vet-specific fields
    all_pets_species = fields.Char(
        string='All Species',
        compute='_compute_pets_summary',
        store=False,
        readonly=True,
        help="All species represented in this encounter"
    )

    # --- VET-SPECIFIC COMPUTE METHODS ---
    @api.depends('patient_ids')
    def _compute_total_pets_count(self):
        for rec in self:
            rec.total_pets_count = len(rec.patient_ids)

    @api.depends('patient_ids')
    def _compute_primary_pet_details(self):
        """Compute details from first/primary pet for backward compatibility"""
        for rec in self:
            primary_pet = rec.patient_ids[:1]  # Take first pet
            if primary_pet:
                # Use correct field names for vet partner fields
                rec.ths_species = getattr(primary_pet, 'ths_species_id', False)
                rec.ths_breed = getattr(primary_pet, 'ths_breed_id', False)
                rec.ths_pet_age = getattr(primary_pet, 'ths_age', False)
                rec.ths_pet_gender = getattr(primary_pet, 'gender', False)
            else:
                rec.ths_species = False
                rec.ths_breed = False
                rec.ths_pet_age = False
                rec.ths_pet_gender = False

    @api.depends('patient_ids')
    def _compute_pets_summary(self):
        """Compute summary information for multiple pets"""
        for rec in self:
            pets = rec.patient_ids
            rec.total_pets_count = len(pets)

            if not pets:
                rec.pets_summary = "No pets"
                rec.all_pets_species = ""
            elif len(pets) == 1:
                rec.pets_summary = pets[0].name
                rec.all_pets_species = pets[0].ths_species_id.name if pets[0].ths_species_id else ""
            else:
                # Show first few pet names
                names = pets[:3].mapped('name')
                if len(pets) > 3:
                    rec.pets_summary = f"{', '.join(names)} and {len(pets) - 3} more"
                else:
                    rec.pets_summary = ', '.join(names)

                # Show all unique species
                species = pets.mapped('ths_species_id.name')
                unique_species = list(set([s for s in species if s]))
                rec.all_pets_species = ', '.join(unique_species) if unique_species else ""

    @api.depends('partner_id')
    def _compute_pet_owner(self):
        """
        For vet practice: sync ths_pet_owner_id with partner_id
        In vet context, partner_id should always be the pet owner (billing customer)
        """
        for rec in self:
            if rec.partner_id and rec.partner_id.ths_partner_type_id.name == 'Pet Owner':
                rec.ths_pet_owner_id = rec.partner_id
            else:
                rec.ths_pet_owner_id = False

    def _inverse_pet_owner(self):
        """
        For vet practice: when pet owner changes, update partner_id (billing customer)
        """
        for rec in self:
            if rec.ths_pet_owner_id:
                rec.partner_id = rec.ths_pet_owner_id

    @api.depends('ths_pet_owner_id')
    def _compute_patient_domain(self):
        """
        Compute domain for pets based on selected owner
        """
        for rec in self:
            if rec.ths_pet_owner_id:
                # Filter pets by selected owner
                rec.patient_ids_domain = str([
                    ('ths_pet_owner_id', '=', rec.ths_pet_owner_id.id),
                    ('ths_partner_type_id.name', '=', 'Pet')
                ])
            else:
                # Show all pets when no owner selected
                rec.patient_ids_domain = str([('ths_partner_type_id.name', '=', 'Pet')])

    # --- VET-SPECIFIC ONCHANGE METHODS ---

    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_filter_pets(self):
        """
        When owner changes, filter available pets and update billing customer
        """
        if self.ths_pet_owner_id:
            # Set as main billing customer
            self.partner_id = self.ths_pet_owner_id

            # Find pets for this owner
            pets = self.env['res.partner'].search([
                ('ths_partner_type_id.name', '=', 'Pet'),
                ('ths_pet_owner_id', '=', self.ths_pet_owner_id.id)
            ])

            # Clear current pet selection - user will reselect appropriate pets
            self.patient_ids = [Command.clear()]

            # Update domain to show only this owner's pets
            return {
                'domain': {
                    'patient_ids': [('id', 'in', pets.ids)] if pets else [('id', '=', False)]
                }
            }
        else:
            # Clear billing customer if no owner
            self.partner_id = False
            # Show all pets when no owner selected
            return {
                'domain': {
                    'patient_ids': [('ths_partner_type_id.name', '=', 'Pet')]
                }
            }

    @api.onchange('patient_ids')
    def _onchange_patient_sync_owner(self):
        """
        When pets are selected, auto-set owner if all pets have same owner
        """
        if self.patient_ids:
            owners = self.patient_ids.mapped('ths_pet_owner_id')
            unique_owners = list(set(owners.ids)) if owners else []

            if len(unique_owners) == 1 and not self.ths_pet_owner_id:
                # All pets have same owner - auto-set it
                self.ths_pet_owner_id = owners[0]
                self.partner_id = owners[0]  # Set as billing customer
            elif len(unique_owners) > 1:
                # Multiple owners - show warning and require manual selection
                return {
                    'warning': {
                        'title': _('Multiple Pet Owners'),
                        'message': _(
                            'Selected pets belong to different owners. Please select pets from the same owner or choose the primary owner for billing.')
                    }
                }

        # Explicit return for PyCharm
        return None

    @api.onchange('partner_id')
    def _onchange_partner_id_sync_owner(self):
        """
        When partner_id changes, sync with ths_pet_owner_id
        """
        if self.partner_id and self.partner_id != self.ths_pet_owner_id:
            # Check if partner_id is a valid pet owner
            if self.partner_id.ths_partner_type_id.name == 'Pet Owner':
                self.ths_pet_owner_id = self.partner_id
            elif self.partner_id.ths_partner_type_id.name == 'Pet':
                # If a pet is selected as partner_id, get its owner
                if self.partner_id.ths_pet_owner_id:
                    self.ths_pet_owner_id = self.partner_id.ths_pet_owner_id
                    self.partner_id = self.partner_id.ths_pet_owner_id  # Set owner as billing customer
                    return {
                        'warning': {
                            'title': _('Pet Selected as Billing Customer'),
                            'message': _(
                                'A pet was selected as billing customer. Changed to pet owner: %s',
                                self.ths_pet_owner_id.name)
                        }
                    }

        # Explicit return for PyCharm
        return None

    # --- OVERRIDE CREATE/WRITE FOR VET WORKFLOW ---

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to handle vet-specific partner/patient relationships
        """
        processed_vals_list = []
        for vals in vals_list:
            # For vet practice: ensure proper owner/pet relationships
            if vals.get('ths_pet_owner_id') and not vals.get('partner_id'):
                # Set pet owner as billing customer
                vals['partner_id'] = vals['ths_pet_owner_id']

            if vals.get('partner_id') and not vals.get('ths_pet_owner_id'):
                # Sync owner field with billing customer
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.ths_partner_type_id.name == 'Pet Owner':
                    vals['ths_pet_owner_id'] = vals['partner_id']
                elif partner.ths_partner_type_id.name == 'Pet' and partner.ths_pet_owner_id:
                    # If pet selected as partner, use its owner
                    vals['ths_pet_owner_id'] = partner.ths_pet_owner_id.id
                    vals['partner_id'] = partner.ths_pet_owner_id.id

            processed_vals_list.append(vals)

        return super().create(processed_vals_list)

    def write(self, vals):
        """
        Override write to maintain vet-specific relationships
        """
        # For vet practice: maintain partner_id = pet owner relationship
        if 'ths_pet_owner_id' in vals and 'partner_id' not in vals:
            vals['partner_id'] = vals['ths_pet_owner_id']

        if 'partner_id' in vals and 'ths_pet_owner_id' not in vals:
            # Ensure partner_id is always a pet owner
            if vals['partner_id']:
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.ths_partner_type_id.name == 'Pet Owner':
                    vals['ths_pet_owner_id'] = vals['partner_id']
                elif partner.ths_partner_type_id.name == 'Pet' and partner.ths_pet_owner_id:
                    vals['ths_pet_owner_id'] = partner.ths_pet_owner_id.id
                    vals['partner_id'] = partner.ths_pet_owner_id.id

        return super().write(vals)

    # --- VET-SPECIFIC CONSTRAINT VALIDATIONS ---

    @api.constrains('patient_ids', 'ths_pet_owner_id', 'partner_id')
    def _check_vet_encounter_consistency(self):
        """
        Validate vet encounter consistency:
        1. All pets must belong to the same owner
        2. partner_id must be the pet owner (billing customer)
        3. ths_pet_owner_id must match partner_id
        """
        for encounter in self:
            if encounter.patient_ids:
                # Check 1: All pets must have the same owner
                pet_owners = encounter.patient_ids.mapped('ths_pet_owner_id')
                unique_owners = list(set(pet_owners.ids)) if pet_owners else []

                if len(unique_owners) > 1:
                    owner_names = [owner.name for owner in pet_owners if owner]
                    raise ValidationError(_(
                        "All pets in an encounter must belong to the same owner. "
                        "Found pets belonging to: %s", ', '.join(set(owner_names))
                    ))

                # Check 2 & 3: Owner consistency with billing
                if unique_owners and encounter.partner_id:
                    expected_owner_id = unique_owners[0]
                    if encounter.partner_id.id != expected_owner_id:
                        expected_owner = self.env['res.partner'].browse(expected_owner_id)
                        raise ValidationError(_(
                            "Billing customer must be the pet owner. "
                            "Expected: %s, Current: %s",
                            expected_owner.name, encounter.partner_id.name
                        ))

                if encounter.ths_pet_owner_id and encounter.partner_id:
                    if encounter.ths_pet_owner_id != encounter.partner_id:
                        raise ValidationError(_(
                            "Pet Owner field must match the billing customer. "
                            "Pet Owner: %s, Billing Customer: %s",
                            encounter.ths_pet_owner_id.name, encounter.partner_id.name
                        ))

    # --- VET-SPECIFIC BUSINESS METHODS ---

    def _get_primary_pet(self):
        """Get the primary/first pet for this encounter"""
        self.ensure_one()
        return self.patient_ids[0] if self.patient_ids else False

    def _get_all_pets_species(self):
        """Get unique species of all pets in this encounter"""
        self.ensure_one()
        return self.patient_ids.mapped('ths_species_id').mapped('name')

    def _get_pet_ages_summary(self):
        """Get age summary for all pets in encounter"""
        self.ensure_one()
        pets_with_ages = []
        for pet in self.patient_ids:
            if hasattr(pet, '_get_pet_age_in_years'):
                age = pet._get_pet_age_in_years()
                if age:
                    pets_with_ages.append(f"{pet.name}: {age}")
        return '; '.join(pets_with_ages) if pets_with_ages else 'Ages not available'

    def action_create_pending_items_for_all_pets(self):
        """
        Create pending POS items for all pets in this encounter
        Follows vet logic: partner_id=Pet Owner (billing), patient_id=individual pet
        """
        self.ensure_one()
        if not self.patient_ids:
            raise UserError(_("No pets selected for this encounter."))

        if not self.ths_pet_owner_id:
            raise UserError(_("Pet owner must be set before creating pending items."))

        # This would create individual pending items for each pet
        # Implementation would depend on the specific pending item creation logic
        # For now, just a placeholder to show the structure

        pending_items = self.env['ths.pending.pos.item']
        for pet in self.patient_ids:
            # Example structure - actual implementation would be more detailed
            item_vals = {
                'encounter_id': self.id,
                'partner_id': self.ths_pet_owner_id.id,  # Pet Owner for billing
                'patient_id': pet.id,  # Individual pet receiving service
                'practitioner_id': self.practitioner_id.id,
                # Other fields would be populated based on services provided
            }
            # pending_items |= self.env['ths.pending.pos.item'].create(item_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pending POS Items'),
            'res_model': 'ths.pending.pos.item',
            'view_mode': 'list,form',
            'domain': [('encounter_id', '=', self.id)],
            'context': {'create': False}
        }

    def action_view_pet_medical_histories(self):
        """View individual medical histories for all pets in this encounter"""
        self.ensure_one()
        if not self.patient_ids:
            return {}

        return {
            'name': _('Pet Medical Histories'),
            'type': 'ir.actions.act_window',
            'res_model': 'ths.medical.base.encounter',
            'view_mode': 'list,form',
            'domain': [('patient_ids', 'in', self.patient_ids.ids)],
            'context': {
                'search_default_groupby_patient': 1,
                'create': False,
            }
        }

    # --- OVERRIDE PENDING ITEM CREATION ---

    def _create_pending_pos_items(self, services_data):
        """
        Override to handle vet-specific pending item creation
        Ensures partner_id=Pet Owner (billing), patient_id=individual pet
        """
        self.ensure_one()
        if not self.ths_pet_owner_id:
            raise UserError(_("Pet owner must be set before creating pending items."))

        pending_items = self.env['ths.pending.pos.item']

        for service_data in services_data:
            # For vet practice: each service can be for a specific pet
            pet_id = service_data.get('pet_id') or (self.patient_ids[0].id if self.patient_ids else False)

            if not pet_id:
                raise UserError(_("Pet must be specified for each service in veterinary practice."))

            item_vals = {
                'encounter_id': self.id,
                'appointment_id': self.appointment_id.id if self.appointment_id else False,
                'partner_id': self.ths_pet_owner_id.id,  # Pet Owner (billing customer)
                'patient_id': pet_id,  # Individual pet receiving service
                'product_id': service_data.get('product_id'),
                'description': service_data.get('description', ''),
                'qty': service_data.get('qty', 1.0),
                'price_unit': service_data.get('price_unit', 0.0),
                'discount': service_data.get('discount', 0.0),
                'practitioner_id': self.practitioner_id.id,
                'commission_pct': service_data.get('commission_pct', 0.0),
                'state': 'pending',
                'notes': service_data.get('notes', ''),
            }

            pending_items |= pending_items.create(item_vals)

        return pending_items

    # TODO: Add vet-specific encounter methods
    def action_create_vaccination_records(self):
        """Create vaccination records for pets in this encounter"""
        # TODO: Implement vaccination record creation
        pass

    def action_schedule_follow_up_for_pets(self):
        """Schedule follow-up appointments for pets"""
        # TODO: Implement follow-up scheduling for individual pets
        pass

    def action_create_treatment_plan(self):
        """Create treatment plan for pets"""
        # TODO: Implement treatment plan creation
        pass
