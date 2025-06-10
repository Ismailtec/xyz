# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ThsPendingPosItem(models.Model):
    _inherit = 'ths.pending.pos.item'

    # Override fields for vet context with proper domains and labels
    partner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',  # Relabeled for vet context
        store=True,
        index=True,
        required=True,
        domain="[('ths_partner_type_id.name', '=', 'Pet Owner')]",
        help="The pet owner responsible for payment and billing."
    )

    patient_id = fields.Many2one(
        'res.partner',
        string='Pet',  # Relabeled for vet context
        store=True,
        index=True,
        required=True,
        domain="[('ths_partner_type_id.name', '=', 'Pet')]",
        help="The pet who received the service/product."
    )

    # Add vet-specific field for boarding integration
    boarding_stay_id = fields.Many2one(
        'vet.boarding.stay',
        string='Source Boarding Stay',
        ondelete='cascade',
        index=True,
        copy=False,
        help="Boarding stay that generated this billing item (if applicable)."
    )

    # Add pet owner related field for easier reporting
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner (Billing)',
        related='partner_id',
        store=True,
        readonly=True,
        help="Pet owner responsible for billing - same as partner_id in vet practice."
    )

    # Add pet-related fields for reporting
    pet_species_id = fields.Many2one(
        'ths.species',
        string='Pet Species',
        related='patient_id.ths_species_id',
        store=False,
        readonly=True,
        help="Species of the pet receiving the service."
    )

    pet_breed_id = fields.Many2one(
        'ths.breed',
        string='Pet Breed',
        related='patient_id.ths_breed_id',
        store=False,
        readonly=True,
        help="Breed of the pet receiving the service."
    )

    pet_age = fields.Char(
        string='Pet Age',
        related='patient_id.ths_age',
        store=False,
        readonly=True,
        help="Age of the pet receiving the service."
    )

    # --- VET-SPECIFIC COMPUTE METHODS ---

    @api.depends('product_id', 'encounter_id', 'patient_id', 'partner_id')
    def _compute_name(self):
        """Override to show vet-specific naming: Product - Pet (Owner)"""
        for item in self:
            name = item.product_id.name or _("Pending Item")

            # Add pet name
            if item.patient_id:
                name += f" - {item.patient_id.name}"

            # Add owner name in parentheses
            if item.partner_id:
                name += f" ({item.partner_id.name})"

            # Add encounter reference
            if item.encounter_id:
                name += f" [{item.encounter_id.name}]"

            item.name = name

    # --- VET-SPECIFIC CONSTRAINT VALIDATIONS ---

    @api.constrains('partner_id', 'patient_id')
    def _check_pet_owner_relationship(self):
        """
        For vet practice: ensure patient (pet) belongs to partner (pet owner)
        """
        for item in self:
            if item.partner_id and item.patient_id:
                # Check if pet belongs to the specified owner
                if item.patient_id.ths_pet_owner_id and item.patient_id.ths_pet_owner_id != item.partner_id:
                    raise UserError(_(
                        "Pet ownership mismatch: Pet '%s' belongs to '%s' but item is assigned to owner '%s'.",
                        item.patient_id.name,
                        item.patient_id.ths_pet_owner_id.name,
                        item.partner_id.name
                    ))

    @api.constrains('encounter_id', 'partner_id', 'patient_id')
    def _check_encounter_consistency(self):
        """
        Validate that the pending item is consistent with its source encounter
        """
        for item in self:
            if item.encounter_id:
                encounter = item.encounter_id

                # Check pet owner consistency
                if encounter.partner_id and item.partner_id != encounter.partner_id:
                    raise UserError(_(
                        "Pet owner mismatch: Item owner '%s' doesn't match encounter owner '%s'.",
                        item.partner_id.name, encounter.partner_id.name
                    ))

                # Check pet consistency
                if encounter.patient_ids and item.patient_id not in encounter.patient_ids:
                    raise UserError(_(
                        "Pet mismatch: Pet '%s' is not included in the source encounter pets.",
                        item.patient_id.name
                    ))

    # --- VET-SPECIFIC ONCHANGE METHODS ---

    @api.onchange('partner_id')
    def _onchange_partner_id_filter_pets(self):
        """
        When pet owner changes, filter available pets to only show pets owned by this owner
        """
        if self.partner_id:
            # Filter pets belonging to this owner
            domain = [
                ('ths_partner_type_id.name', '=', 'Pet'),
                ('ths_pet_owner_id', '=', self.partner_id.id)
            ]

            # Clear current pet selection if it doesn't belong to the new owner
            if self.patient_id and self.patient_id.ths_pet_owner_id != self.partner_id:
                self.patient_id = False

            return {'domain': {'patient_id': domain}}
        else:
            # Show all pets when no owner selected
            return {'domain': {'patient_id': [('ths_partner_type_id.name', '=', 'Pet')]}}

    @api.onchange('patient_id')
    def _onchange_patient_id_auto_set_owner(self):
        """
        When pet changes, auto-set the pet owner if not already set
        """
        if self.patient_id and self.patient_id.ths_pet_owner_id:
            if not self.partner_id:
                self.partner_id = self.patient_id.ths_pet_owner_id
            elif self.partner_id != self.patient_id.ths_pet_owner_id:
                return {
                    'warning': {
                        'title': _('Pet Owner Mismatch'),
                        'message': _(
                            "Selected pet '%s' belongs to '%s', but the current owner is '%s'. "
                            "Please select a pet that belongs to the current owner or change the owner.",
                            self.patient_id.name,
                            self.patient_id.ths_pet_owner_id.name,
                            self.partner_id.name
                        )
                    }
                }

    @api.onchange('encounter_id')
    def _onchange_encounter_id_sync_data(self):
        """
        When encounter changes, sync pet owner and available pets
        """
        if self.encounter_id:
            encounter = self.encounter_id

            # Auto-set pet owner from encounter
            if encounter.partner_id and not self.partner_id:
                self.partner_id = encounter.partner_id

            # Filter pets to only those in the encounter
            if encounter.patient_ids:
                domain = [('id', 'in', encounter.patient_ids.ids)]

                # Auto-set pet if only one pet in encounter
                if len(encounter.patient_ids) == 1 and not self.patient_id:
                    self.patient_id = encounter.patient_ids[0]

                return {'domain': {'patient_id': domain}}

    # --- VET-SPECIFIC HELPER METHODS ---

    def _get_pet_info_summary(self):
        """Get a summary of pet information for display"""
        self.ensure_one()
        if not self.patient_id:
            return "No pet assigned"

        pet = self.patient_id
        info_parts = [pet.name]

        if pet.ths_species_id:
            info_parts.append(pet.ths_species_id.name)

        if pet.ths_breed_id:
            info_parts.append(pet.ths_breed_id.name)

        if pet.ths_age:
            info_parts.append(f"{pet.ths_age} old")

        return " • ".join(info_parts)

    def _validate_vet_business_rules(self):
        """Validate vet-specific business rules"""
        self.ensure_one()

        errors = []

        # Check pet-owner relationship
        if self.patient_id and self.partner_id:
            if (self.patient_id.ths_pet_owner_id and
                    self.patient_id.ths_pet_owner_id != self.partner_id):
                errors.append(
                    f"Pet '{self.patient_id.name}' doesn't belong to owner '{self.partner_id.name}'"
                )

        # Check encounter consistency
        if self.encounter_id:
            if (self.encounter_id.partner_id and
                    self.partner_id != self.encounter_id.partner_id):
                errors.append(
                    f"Item owner doesn't match encounter owner"
                )

            if (self.encounter_id.patient_ids and
                    self.patient_id not in self.encounter_id.patient_ids):
                errors.append(
                    f"Pet is not included in the source encounter"
                )

        return errors

    # --- OVERRIDE ACTIONS FOR VET CONTEXT ---

    def action_cancel(self):
        """ Override to add vet-specific logging """
        super().action_cancel()

        # Add vet-specific message
        for item in self:
            if item.patient_id and item.partner_id:
                item.message_post(body=_(
                    "Veterinary billing item cancelled for pet '%s' (owner: '%s').",
                    item.patient_id.name, item.partner_id.name
                ))

        return True

    # TODO: Add vet-specific methods
    def action_create_medical_record_entry(self):
        """Create a medical record entry for this service"""
        # TODO: Implement medical record integration
        pass

    def action_update_pet_file(self):
        """Update pet's medical file with this service information"""
        # TODO: Implement pet file updates
        pass
