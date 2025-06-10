# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ThsMedicalEncounter(models.Model):
    _inherit = 'ths.medical.base.encounter'

    # Override related fields or add computed fields if display needs adjustment
    patient_ids = fields.Many2many(
        'res.partner',
        'medical_encounter_patient_rel',
        'encounter_id',
        'patient_id',
        string='Pets',
        help="Pets seen during this encounter."
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Pet Owner",
        store=True,
        readonly=False,
        index=True,
        help="The owner responsible for the listed pets."
    )

    # Add related fields from Pet for convenience in encounter view/reports
    ths_species = fields.Many2one(
        'ths.species',
        string='Species',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True
    )
    ths_breed = fields.Many2one(
        'ths.breed',
        string='Breed',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True
    )
    ths_pet_age = fields.Char(
        string='Pet Age',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True
    )
    ths_pet_gender = fields.Selection(
        selection=[('male', 'Male'), ('female', 'Female')],
        string='Pet Gender',
        compute='_compute_primary_pet_details',
        store=False,
        readonly=True
    )

    # Count fields for multiple pets
    total_pets_count = fields.Integer(
        string='Total Pets',
        compute='_compute_pets_summary',
        store=False,
        readonly=True
    )
    pets_summary = fields.Char(
        string='Pets Summary',
        compute='_compute_pets_summary',
        store=False,
        readonly=True
    )

    @api.depends('patient_ids')
    def _compute_primary_pet_details(self):
        """Compute details from first/primary pet for backward compatibility"""
        for rec in self:
            primary_pet = rec.patient_ids[:1]  # Take first pet
            if primary_pet:
                # Use correct field names for vet partner fields
                rec.ths_species = primary_pet.ths_species_id if hasattr(primary_pet, 'ths_species_id') else False
                rec.ths_breed = primary_pet.ths_breed_id if hasattr(primary_pet, 'ths_breed_id') else False
                rec.ths_pet_age = primary_pet.ths_age if hasattr(primary_pet, 'ths_age') else False
                rec.ths_pet_gender = primary_pet.gender if hasattr(primary_pet, 'gender') else False
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
            elif len(pets) == 1:
                rec.pets_summary = pets[0].name
            else:
                # Show first few pet names
                names = pets[:3].mapped('name')
                if len(pets) > 3:
                    rec.pets_summary = f"{', '.join(names)} and {len(pets) - 3} more"
                else:
                    rec.pets_summary = ', '.join(names)

    @api.depends('appointment_id', 'appointment_id.ths_patient_ids')
    def _compute_all_fields(self):
        """Compute partner, patients, and practitioner from the appointment."""
        for encounter in self:
            appointment = encounter.appointment_id

            # Get Partner (Customer/Owner) directly from appointment
            if appointment and hasattr(appointment, 'ths_pet_owner_id'):
                encounter.partner_id = appointment.ths_pet_owner_id
            elif appointment:
                encounter.partner_id = appointment.partner_id
            else:
                encounter.partner_id = False

            # Get Patients from Many2many field on appointment
            if appointment and hasattr(appointment, 'ths_patient_ids'):
                encounter.patient_ids = appointment.ths_patient_ids
            else:
                encounter.patient_ids = False

            # Get Practitioner from custom field on appointment
            encounter.practitioner_id = (appointment.ths_practitioner_id
                                         if appointment and hasattr(appointment, 'ths_practitioner_id')
                                         else False)

            # Get Room from custom field on appointment
            encounter.room_id = (appointment.ths_room_id
                                 if appointment and hasattr(appointment, 'ths_room_id')
                                 else False)

    # No major logic changes needed here if calendar_event handles the patient/partner mapping correctly.
    # Specific vet EMR fields could be added here later.

    # TODO: Add vet-specific encounter methods
    # def action_generate_vaccination_schedule(self):
    #     """Generate vaccination schedule for pets in this encounter"""
    #     pass
    #
    # def action_create_follow_up_appointment(self):
    #     """Create follow-up appointment for the same pets"""
    #     pass
