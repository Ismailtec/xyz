# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # Modify domain for ths_patient_ids to primarily show Pets and Relabel field to 'Pets'
    ths_patient_ids = fields.Many2many(
        'res.partner',
        string='Pets',
        compute='_compute_patient_ids',
        inverse='_inverse_patient_ids',
        domain="[('ths_partner_type_id.is_patient', '=', True)]",
        store=True,
        index=True,
        tracking=True,
        help="Pets attending this appointment."
    )

    # Add Pet Owner field, related to the selected Pet
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        #related='ths_patient_ids.ths_pet_owner_id',  # Link via Pet's owner field
        compute='_compute_pet_owner',
        domain="[('ths_partner_type_id.name','=','Pet Owner')]",
        store=True,
        readonly=False,
        index=True,
        help="Main owner responsible for the pets.",
    )
    # Computed domain string for pets
    ths_patient_ids_domain = fields.Char(
        compute='_compute_patient_domain',
        store=True
    )

    @api.depends('partner_ids')
    def _compute_patient_ids(self):
        for rec in self:
            if rec.partner_ids:
                patients = self.env['res.partner'].browse(rec.partner_ids.ids).filtered(
                    lambda p: p.ths_partner_type_id.is_patient)
                rec.ths_patient_ids = patients
            else:
                rec.ths_patient_ids = [Command.clear()]

    def _inverse_patient_ids(self):
        for rec in self:
            if rec.ths_patient_ids:
                rec.partner_ids = [Command.set(rec.ths_patient_ids.ids)]
            else:
                rec.partner_ids = [Command.clear()]

    @api.depends('ths_patient_ids')
    def _compute_pet_owner(self):
        for rec in self:
            if rec.ths_patient_ids:
                owners = rec.ths_patient_ids.mapped('ths_pet_owner_id')
                rec.ths_pet_owner_id = owners[0] if owners else False
            else:
                rec.ths_pet_owner_id = False

    @api.depends('ths_pet_owner_id')
    def _compute_patient_domain(self):
        for rec in self:
            if rec.ths_pet_owner_id:
                rec.ths_patient_ids_domain = str([('ths_pet_owner_id', '=', rec.ths_pet_owner_id.id)])
            else:
                rec.ths_patient_ids_domain = str([('ths_partner_type_id.is_patient', '=', True)])

    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_partner(self):
        if self.ths_pet_owner_id:
            pets = self.env['res.partner'].search([
                ('ths_partner_type_id.is_patient', '=', True),
                ('ths_pet_owner_id', '=', self.ths_pet_owner_id.id)
            ])
            if pets:
                self.ths_patient_ids = [Command.set(pets.ids)]

    @api.onchange('ths_patient_ids')
    def _onchange_patient_sync_owner(self):
        if self.ths_patient_ids:
            owners = self.ths_patient_ids.mapped('ths_pet_owner_id')
            if owners:
                self.ths_pet_owner_id = owners[0]

    @api.onchange('partner_ids')
    def _onchange_partner_ids_to_owner(self):
        if self.partner_ids and not self.ths_pet_owner_id:
            self.ths_pet_owner_id = self.partner_ids[0]


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        partner_ids = self.env.context.get('default_partner_ids') or []
        if partner_ids and 'ths_patient_ids' in fields_list:
            res['ths_patient_ids'] = partner_ids[:1]
        return res

    # Override create/write or add onchange to ensure partner_id is set to owner
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('partner_ids') and not vals.get('ths_patient_ids'):
                vals['ths_patient_ids'] = [Command.set(vals['partner_ids'])]
        return super().create(vals_list)

    def write(self, vals):
        if 'partner_ids' in vals and 'ths_patient_ids' not in vals:
            vals['ths_patient_ids'] = [Command.set(vals['partner_ids'])]
        return super().write(vals)

    # Override prepare encounter vals to ensure correct patient/partner assignment
    def _prepare_encounter_vals(self):
        """ Override to ensure Pets -> patient_ids, Owner -> partner_id """
        self.ensure_one()
        pets = self.ths_patient_ids
        owner_partner = self.ths_pet_owner_id

        if pets and owner_partner:
            for pet in pets:
                if pet.ths_pet_owner_id and pet.ths_pet_owner_id != owner_partner:
                    raise UserError(_(
                        "Consistency Error: Appointment Owner '%s' does not match Pet '%s' Owner '%s'.",
                        owner_partner.name, pet.name, pet.ths_pet_owner_id.name))

        elif pets and not owner_partner:
            unique_owners = pets.mapped('ths_pet_owner_id')
            if len(unique_owners) == 1:
                owner_partner = unique_owners[0]
            else:
                raise UserError(_("Cannot determine a unique owner for the selected pets."))

        if not pets:
            raise UserError(_("Cannot create encounter: Pet(s) not set on the appointment."))
        if not owner_partner:
            raise UserError(_("Cannot create encounter: Pet Owner (Customer) could not be determined."))
        if not self.ths_practitioner_id:
            raise UserError(_("Cannot create encounter: Practitioner is not set on the appointment."))

        return {
            'appointment_id': self.id,
            'state': 'draft',
            'patient_ids': [Command.set(pets.ids)],
            'practitioner_id': self.ths_practitioner_id.id,
            'partner_id': owner_partner.id,
            'chief_complaint': self.ths_reason_for_visit,
        }