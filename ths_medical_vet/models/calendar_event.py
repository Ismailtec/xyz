# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # Modify domain for ths_patient_id to primarily show Pets
    # Allow fallback to Patient/Walk-in if vet module isn't the only use case? Risky.
    # Best practice: Vet module installed = Patient MUST be a Pet.
    ths_patient_id = fields.Many2one(
        'res.partner',
        string='Pet',  # Relabel field
        index=True,
        tracking=True,
        help="The Pet this appointment is for."
        # Remove previous domain: domain="['|', ('ths_partner_type_id.is_patient', '=', True), ('ths_partner_type_id.name', '=', 'Walk-in')]"
    )

    # Add Pet Owner field, related to the selected Pet
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        related='ths_patient_id.ths_pet_owner_id',  # Link via Pet's owner field
        store=True,  # Store for easier access / searching
        readonly=True,
        index=True,
        help="The owner of the selected Pet.",
    )

    # Override create/write or add onchange to ensure partner_id is set to owner
    @api.onchange('ths_patient_id')
    def _onchange_ths_patient_id_vet(self):
        """ When Pet is selected, automatically set the main partner_id to the Owner """
        if self.ths_patient_id and self.ths_patient_id.ths_pet_owner_id:
            if self.partner_id != self.ths_patient_id.ths_pet_owner_id:
                self.partner_id = self.ths_patient_id.ths_pet_owner_id
                # Auto-update partner_ids (attendees) list?
                # Be careful: Removing previous partner might remove legitimate attendees.
                # Simple approach: Ensure Owner is an attendee.
                owner_id = self.ths_patient_id.ths_pet_owner_id.id
                attendee_ids = self.partner_ids.ids
                if owner_id not in attendee_ids:
                    self.partner_ids = [(6, 0, attendee_ids + [owner_id])]  # Use command 6 to replace list
        elif not self.ths_patient_id:
            # If pet is cleared, should we clear the owner (partner_id)? Maybe not.
            pass

    @api.model_create_multi
    def create(self, vals_list):
        """ Ensure partner_id aligns with pet owner on create """
        for vals in vals_list:
            if vals.get('ths_patient_id'):
                pet = self.env['res.partner'].browse(vals['ths_patient_id'])
                if pet.exists() and pet.ths_pet_owner_id:
                    # Set partner_id if not provided or if different from owner
                    if not vals.get('partner_id') or vals.get('partner_id') != pet.ths_pet_owner_id.id:
                        vals['partner_id'] = pet.ths_pet_owner_id.id
                    # Ensure owner is in attendees
                    owner_id = pet.ths_pet_owner_id.id
                    partner_ids_cmd = vals.get('partner_ids', [])
                    current_partner_ids = [cmd[1] for cmd in partner_ids_cmd if cmd[0] == 6]
                    current_partner_ids = current_partner_ids[0] if current_partner_ids else []
                    linked_partner_ids = [cmd[1] for cmd in partner_ids_cmd if cmd[0] == 4]
                    final_partners = set(current_partner_ids) | set(linked_partner_ids) | {owner_id}
                    vals['partner_ids'] = [(6, 0, list(final_partners))]

        return super(CalendarEvent, self).create(vals_list)

    def write(self, vals):
        """ Ensure partner_id aligns with pet owner on write """
        # If patient changes, update partner_id
        if 'ths_patient_id' in vals:
            if vals.get('ths_patient_id'):
                pet = self.env['res.partner'].browse(vals['ths_patient_id'])
                if pet.exists() and pet.ths_pet_owner_id:
                    vals['partner_id'] = pet.ths_pet_owner_id.id
                    # Also update attendees
                    owner_id = pet.ths_pet_owner_id.id
                    current_attendee_ids = self.partner_ids.ids  # Read current attendees before write
                    final_partners = set(current_attendee_ids) | {owner_id}
                    vals['partner_ids'] = [(6, 0, list(final_partners))]
            else:
                # If pet is cleared, what happens to partner_id? Clear it? Keep last?
                # Let's keep it for now unless specified otherwise.
                pass

        # If partner changes directly, ensure it's a valid owner if a pet is set?
        # This could get complex, maybe add constraint instead.
        if 'partner_id' in vals and self.ths_patient_id and self.ths_patient_id.ths_pet_owner_id:
            if vals.get('partner_id') != self.ths_patient_id.ths_pet_owner_id.id:
                # Potentially raise error or automatically revert partner_id back to owner
                _logger.warning("Attempted to set appointment partner different from Pet's Owner.")
                vals['partner_id'] = self.ths_patient_id.ths_pet_owner_id.id  # Force back to owner

        return super(CalendarEvent, self).write(vals)

    # Override prepare encounter vals to ensure correct patient/partner assignment
    def _prepare_encounter_vals(self):
        """ Override to ensure Pet -> patient_id, Owner -> partner_id """
        self.ensure_one()
        pet_patient = self.ths_patient_id
        owner_partner = self.ths_pet_owner_id  # Should be owner due to logic above

        # Validate owner matches pet's owner if both set
        if pet_patient and owner_partner and pet_patient.ths_pet_owner_id and pet_patient.ths_pet_owner_id != owner_partner:
            raise UserError(_("Consistency Error: Appointment Customer '%s' does not match Pet '%s' Owner '%s'.",
                              owner_partner.name, pet_patient.name, pet_patient.ths_pet_owner_id.name))
        elif pet_patient and not owner_partner and pet_patient.ths_pet_owner_id:
            # If owner was somehow cleared but pet is set, use pet's owner
            owner_partner = pet_patient.ths_pet_owner_id

        if not pet_patient:
            raise UserError(_("Cannot create encounter: Pet (Patient) is not set on the appointment."))
        if not owner_partner:
            # This case should ideally be prevented by constraints/onchanges
            raise UserError(_("Cannot create encounter: Pet Owner (Customer) could not be determined."))
        if not self.ths_practitioner_id:
            raise UserError(_("Cannot create encounter: Practitioner is not set on the appointment."))

        return {
            'appointment_id': self.id,
            'state': 'draft',
            'patient_id': pet_patient.id,  # Explicitly set Pet as patient
            'practitioner_id': self.ths_practitioner_id.id,
            'partner_id': owner_partner.id,  # Explicitly set Owner as partner
            #'company_id': self.company_id.id or self.env.company.id,
            'chief_complaint': self.ths_reason_for_visit,
        }
