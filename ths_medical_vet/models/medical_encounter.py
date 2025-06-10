# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ThsMedicalEncounter(models.Model):
    _inherit = 'ths.medical.base.encounter'

    # Override fields for vet context with proper labels and domains
    patient_ids = fields.Many2many(
        'res.partner',
        'medical_encounter_patient_rel',
        'encounter_id',
        'patient_id',
        string='Pets',  # Relabeled for vet context
        domain="[('ths_partner_type_id.name', '=', 'Pet')]",
        store=True,
        index=True,
        readonly=True,
        help="Pets seen during this veterinary encounter."
    )

    partner_id = fields.Many2one(
        'res.partner',
        string="Pet Owner",  # Relabeled for vet context
        store=True,
        readonly=True,
        index=True,
        domain="[('ths_partner_type_id.name', '=', 'Pet Owner')]",
        help="The pet owner responsible for billing and payment."
    )

    # Add vet-specific pet owner field synced with partner_id
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner (Billing)',
        related='partner_id',
        store=True,
        readonly=True,
        help="Pet owner responsible for billing - same as partner_id in vet practice."
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

    @api.depends('appointment_id', 'appointment_id.ths_patient_ids', 'appointment_id.ths_pet_owner_id')
    def _compute_all_fields(self):
        """
        Compute partner, patients, and practitioner from the appointment.
        For vet practice: partner_id = pet owner, patient_ids = pets
        """
        for encounter in self:
            appointment = encounter.appointment_id

            # For vet practice: partner_id = pet owner (billing customer)
            if appointment and hasattr(appointment, 'ths_pet_owner_id'):
                encounter.partner_id = appointment.ths_pet_owner_id
            elif appointment:
                # Fallback to partner_id if ths_pet_owner_id not available
                encounter.partner_id = appointment.partner_id
            else:
                encounter.partner_id = False

            # For vet practice: patient_ids = pets (service recipients)
            if appointment and hasattr(appointment, 'ths_patient_ids'):
                encounter.patient_ids = appointment.ths_patient_ids
            else:
                encounter.patient_ids = False

            # Get Practitioner from appointment
            encounter.practitioner_id = (appointment.ths_practitioner_id
                                         if appointment and hasattr(appointment, 'ths_practitioner_id')
                                         else False)

            # Get Room from appointment
            encounter.room_id = (appointment.ths_room_id
                                 if appointment and hasattr(appointment, 'ths_room_id')
                                 else False)

    # --- OVERRIDE BILLING ACTIONS FOR VET CONTEXT ---

    def action_ready_for_billing(self):
        """
        Override to ensure proper vet billing relationships:
        - partner_id = pet owner (billing customer)
        - patient_id = individual pet per line (service recipient)
        """
        PendingItem = self.env['ths.pending.pos.item']
        items_created_count = 0
        encounters_to_process = self.filtered(lambda enc: enc.state in ('draft', 'in_progress'))

        if not encounters_to_process:
            raise UserError(_("No encounters in 'Draft' or 'In Progress' state selected."))

        for encounter in encounters_to_process:
            if not encounter.service_line_ids:
                self._logger.warning(
                    f"Encounter {encounter.name} has no service lines defined. Cannot mark as Ready for Billing without items.")
                continue

            # Use a list to collect vals for batch creation
            pending_item_vals_list = []
            for line in encounter.service_line_ids:
                # --- VET-SPECIFIC VALIDATION CHECKS ---
                if not line.product_id:
                    raise UserError(_("Service line is missing a Product/Service."))
                if line.quantity <= 0:
                    raise UserError(
                        _("Service line for product '%s' has zero or negative quantity.", line.product_id.name))

                # Ensure provider is set (crucial for commissions)
                practitioner = line.practitioner_id or encounter.practitioner_id
                if not practitioner:
                    raise UserError(
                        _("Provider is not set on service line for product '%s' and no default practitioner on encounter '%s'.",
                          line.product_id.name, encounter.name))

                # Ensure pets are set
                pets = encounter.patient_ids
                if not pets:
                    raise UserError(_("No pets set on encounter '%s'.", encounter.name))

                # Ensure pet owner is set
                pet_owner = encounter.partner_id  # In vet practice, this is the pet owner
                if not pet_owner:
                    raise UserError(_("Pet owner is not set on encounter '%s'.", encounter.name))

                # TODO: Handle multiple pets scenario - for now use first pet per line
                # In future, might want to split lines per pet or allow selecting specific pet per line
                primary_pet = pets[0]

                # Validate pet ownership
                if primary_pet.ths_pet_owner_id and primary_pet.ths_pet_owner_id != pet_owner:
                    raise UserError(_(
                        "Pet ownership mismatch: Pet '%s' belongs to '%s' but encounter is for owner '%s'.",
                        primary_pet.name, primary_pet.ths_pet_owner_id.name, pet_owner.name
                    ))
                # --- End VET-SPECIFIC Validation Checks ---

                item_vals = {
                    'encounter_id': encounter.id,
                    'partner_id': pet_owner.id,  # Pet owner (billing customer)
                    'patient_id': primary_pet.id,  # Pet (service recipient)
                    'product_id': line.product_id.id,
                    'description': line.description,
                    'qty': line.quantity,
                    'price_unit': line.price_unit,
                    'discount': line.discount,
                    'practitioner_id': practitioner.id,
                    'room_id': encounter.room_id.id if encounter.room_id else False,
                    'commission_pct': line.commission_pct,
                    'state': 'pending',
                    'notes': line.notes,
                }
                pending_item_vals_list.append(item_vals)

            if pending_item_vals_list:
                try:
                    created_items = PendingItem.sudo().create(pending_item_vals_list)
                    items_created_count += len(created_items)
                    self._logger.info(
                        f"Created {len(created_items)} pending POS items for vet encounter {encounter.name}.")
                    encounter.message_post(body=_("%d items marked as pending for POS billing.", len(created_items)))
                except Exception as e:
                    self._logger.error(f"Failed to create pending POS items for vet encounter {encounter.name}: {e}")
                    raise UserError(_("Failed to create pending POS items for encounter %s: %s", encounter.name, e))

            # Update encounter state
            encounter.write({'state': 'ready_for_billing'})

        if items_created_count > 0:
            self._logger.info(
                f"Successfully processed {len(encounters_to_process)} vet encounters, created {items_created_count} total pending POS items.")
        return True

    # --- VET-SPECIFIC CONSTRAINT VALIDATIONS ---
    @api.constrains('patient_ids', 'partner_id')
    def _check_vet_encounter_consistency(self):
        """
        Validate vet encounter consistency:
        1. All pets must belong to the same owner
        2. partner_id must be the pet owner
        """
        for encounter in self:
            if encounter.patient_ids and encounter.partner_id:
                # Check 1: All pets must belong to the same owner
                pet_owners = encounter.patient_ids.mapped('ths_pet_owner_id')
                unique_owners = list(set(pet_owners.ids)) if pet_owners else []

                if len(unique_owners) > 1:
                    owner_names = [owner.name for owner in pet_owners if owner]
                    raise UserError(_(
                        "All pets in encounter '%s' must belong to the same owner. "
                        "Found pets belonging to: %s",
                        encounter.name, ', '.join(set(owner_names))
                    ))

                # Check 2: partner_id must be the pet owner
                if unique_owners and encounter.partner_id.id not in unique_owners:
                    expected_owner = self.env['res.partner'].browse(unique_owners[0])
                    raise UserError(_(
                        "Encounter billing customer must be the pet owner. "
                        "Expected: %s, Current: %s",
                        expected_owner.name, encounter.partner_id.name
                    ))

    # --- VET-SPECIFIC HELPER METHODS ---
    def _get_primary_pet(self):
        """Get the primary/first pet for this encounter"""
        self.ensure_one()
        return self.patient_ids[0] if self.patient_ids else False

    def _get_pet_owner(self):
        """Get the pet owner (billing customer) for this encounter"""
        self.ensure_one()
        return self.partner_id

    def _get_all_pets_by_species(self):
        """Get pets grouped by species"""
        self.ensure_one()
        pets_by_species = {}
        for pet in self.patient_ids:
            species = pet.ths_species_id.name if pet.ths_species_id else 'Unknown'
            if species not in pets_by_species:
                pets_by_species[species] = []
            pets_by_species[species].append(pet)
        return pets_by_species

    def _validate_pet_ownership(self):
        """Validate that all pets belong to the billing customer"""
        self.ensure_one()
        if not self.patient_ids or not self.partner_id:
            return True

        for pet in self.patient_ids:
            if pet.ths_pet_owner_id and pet.ths_pet_owner_id != self.partner_id:
                return False
        return True

    # TODO: Add vet-specific encounter methods
    def action_generate_vaccination_schedule(self):
        """Generate vaccination schedule for pets in this encounter"""
        # TODO: Implement vaccination schedule generation
        pass

    def action_create_follow_up_appointment(self):
        """Create follow-up appointment for the same pets and owner"""
        # TODO: Implement follow-up appointment creation
        pass

    def action_create_boarding_request(self):
        """Create boarding request for pets if needed"""
        # TODO: Implement boarding request creation
        pass

    def action_update_pet_medical_history(self):
        """Update medical history records for all pets in encounter"""
        # TODO: Implement medical history updates
        pass
