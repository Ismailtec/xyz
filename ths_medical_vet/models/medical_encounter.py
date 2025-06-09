# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ThsMedicalEncounter(models.Model):
    _inherit = 'ths.medical.base.encounter'

    # Override related fields or add computed fields if display needs adjustment
    patient_ids = fields.Many2many(
        'res.partner',
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

    @api.depends('patient_ids')
    def _compute_primary_pet_details(self):
        for rec in self:
            first_pet = rec.patient_ids[:1]
            rec.ths_species = first_pet.ths_species_id if first_pet else False
            rec.ths_breed = first_pet.ths_breed_id if first_pet else False
            rec.ths_pet_age = first_pet.ths_age if first_pet else False
            rec.ths_pet_gender = first_pet.gender if first_pet else False

    # No major logic changes needed here if calendar_event handles the patient/partner mapping correctly.
    # Specific vet EMR fields could be added here later.
