# -*- coding: utf-8 -*-

from odoo import models, fields


class ThsMedicalEncounter(models.Model):
    _inherit = 'ths.medical.base.encounter'

    # Override related fields or add computed fields if display needs adjustment
    patient_id = fields.Many2one(
        string="Pet"  # Relabel
        # Keep related link, should be populated correctly by calendar_event override
    )
    partner_id = fields.Many2one(
        string="Pet Owner"  # Relabel
        # Keep related link
    )

    # Add related fields from Pet for convenience in encounter view/reports
    ths_species = fields.Many2one(related='patient_id.ths_species_id', string='Species', store=False, readonly=True)
    ths_breed = fields.Many2one(related='patient_id.ths_breed_id', string='Breed', store=False, readonly=True)
    ths_pet_age = fields.Char(related='patient_id.ths_age', string='Pet Age', store=False, readonly=True)
    ths_pet_gender = fields.Selection(related='patient_id.gender', string='Pet Gender', store=False, readonly=True)

    # No major logic changes needed here if calendar_event handles the patient/partner mapping correctly.
    # Specific vet EMR fields could be added here later.
