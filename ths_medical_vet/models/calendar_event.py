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
        'calendar_event_patient_rel',  # Use same relation table as base
        'event_id',
        'patient_id',
        string='Pets',  # Relabeled for veterinary context
        compute='_compute_patient_ids',
        inverse='_inverse_patient_ids',
        domain="[('ths_partner_type_id.name', '=', 'Pet')]",  # Filter for pets only
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
                patients = rec.partner_ids.filtered(
                    lambda p: p.ths_partner_type_id.name == 'Pet')
                rec.ths_patient_ids = [Command.set(patients.ids)] if patients else [Command.clear()]
            else:
                rec.ths_patient_ids = [Command.clear()]

    def _inverse_patient_ids(self):
        for rec in self:
            if rec.ths_patient_ids:
                partner_ids = rec.ths_patient_ids.ids.copy()
                if rec.ths_pet_owner_id:
                    partner_ids.append(rec.ths_pet_owner_id.id)
                rec.partner_ids = [Command.set(list(set(partner_ids)))]
            else:
                rec.partner_ids = [Command.clear()]

    @api.depends('ths_patient_ids')
    def _compute_pet_owner(self):
        for rec in self:
            if rec.ths_patient_ids:
                # Get owners from selected pets
                owners = rec.ths_patient_ids.mapped('ths_pet_owner_id')
                # TODO: Handle multiple owners scenario - for now take first unique owner
                unique_owners = list(set(owners.ids)) if owners else []
                rec.ths_pet_owner_id = owners if len(unique_owners) == 1 else False
            else:
                rec.ths_pet_owner_id = False

    @api.depends('ths_pet_owner_id')
    def _compute_patient_domain(self):
        for rec in self:
            if rec.ths_pet_owner_id:
                # Filter pets by selected owner
                rec.ths_patient_ids_domain = str([('ths_pet_owner_id', '=', rec.ths_pet_owner_id.id)])
            else:
                # Show all pets
                rec.ths_patient_ids_domain = str([('ths_partner_type_id.name', '=', 'Pet')])

    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_filter_pets(self):
        """When owner changes, filter available pets and clear current selection"""
        if self.ths_pet_owner_id:
            # Find pets for this owner
            pets = self.env['res.partner'].search([
                ('ths_partner_type_id.name', '=', 'Pet'),
                ('ths_pet_owner_id', '=', self.ths_pet_owner_id.id)
            ])
            # Clear current selection - user will reselect appropriate pets
            #self.ths_patient_ids = [Command.clear()]

            # Update domain to show only this owner's pets
            return {
                'domain': {
                    'ths_patient_ids': [('id', 'in', pets.ids)] if pets else [('id', '=', False)]
                }
            }
        else:
            # Show all pets when no owner selected
            return {
                'domain': {
                    'ths_patient_ids': [('ths_partner_type_id.name', '=', 'Pet')]
                }
            }

    @api.onchange('ths_patient_ids')
    def _onchange_patient_sync_owner(self):
        """When pets are selected, auto-set owner if all pets have same owner"""
        if self.ths_patient_ids:
            owners = self.ths_patient_ids.mapped('ths_pet_owner_id')
            unique_owners = list(set(owners.ids)) if owners else []

            if len(unique_owners) == 1:
                # All pets have same owner - auto-set it
                self.ths_pet_owner_id = owners
            elif len(unique_owners) > 1:
                # Multiple owners - user needs to choose or we can show warning
                # For now, clear owner selection
                self.ths_pet_owner_id = False
                # TODO: Could show warning message about multiple owners

    @api.onchange('partner_ids')
    def _onchange_partner_ids_to_owner(self):
        """Extract pet owner from partner_ids if pets are included"""
        if self.partner_ids and not self.ths_pet_owner_id:
            # Look for pet owners in partner_ids
            owners = self.partner_ids.filtered(
                lambda p: p.ths_partner_type_id.name == 'Pet Owner')
            if owners:
                self.ths_pet_owner_id = owners


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Handle default partner_ids for Many2many field
        partner_ids = self.env.context.get('default_partner_ids') or []
        if partner_ids and 'ths_patient_ids' in fields_list:
            # Filter to only include pets from the default partners
            partners = self.env['res.partner'].browse(partner_ids)
            pets = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet')
            if pets:
                res['ths_patient_ids'] = [Command.set(pets.ids)]

                # Auto-set owner if pets have common owner
                owners = pets.mapped('ths_pet_owner_id')
                if len(set(owners.ids)) == 1:
                    res['ths_pet_owner_id'] = owners.id
        return res

    # Override create/write or add onchange to ensure partner_id is set to owner
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Handle Many2many field creation
            if vals.get('ths_patient_ids') and not vals.get('partner_ids'):
                patient_ids = []
                # for cmd in vals['ths_patient_ids']:
                #     if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == Command.SET:
                #         patient_ids.extend(cmd[2] if cmd[2] else [])

                if patient_ids:
                    partner_ids = patient_ids.copy()
                    # Add owner if specified
                    if vals.get('ths_pet_owner_id'):
                        partner_ids.append(vals['ths_pet_owner_id'])
                    vals['partner_ids'] = [Command.set(list(set(partner_ids)))]

        return super().create(vals_list)

    def write(self, vals):
        # Handle Many2many field updates
        if 'ths_patient_ids' in vals:
            # Extract patient IDs from Many2many commands
            patient_ids = []
            # if vals['ths_patient_ids']:
            #     for cmd in vals['ths_patient_ids']:
            #         if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == Command.SET:
            #             patient_ids.extend(cmd[2] if cmd[2] else [])

            # Update partner_ids to include pets and owner
            if 'partner_ids' not in vals:
                partner_ids = patient_ids.copy()
                # Add current or specified owner
                owner_id = vals.get('ths_pet_owner_id') or self.ths_pet_owner_id.id
                if owner_id:
                    partner_ids.append(owner_id)
                vals['partner_ids'] = [Command.set(list(set(partner_ids)))]

        return super().write(vals)

    # Override prepare encounter vals to ensure correct patient/partner assignment
    def _prepare_encounter_vals(self):
        """ Override to ensure Pets -> patient_ids, Owner -> partner_id """
        self.ensure_one()
        pets = self.ths_patient_ids
        owner_partner = self.ths_pet_owner_id

        if pets and owner_partner:
            # Validate that all pets belong to the selected owner
            for pet in pets:
                if pet.ths_pet_owner_id and pet.ths_pet_owner_id != owner_partner:
                    raise UserError(_(
                        "Consistency Error: Appointment Owner '%s' does not match Pet '%s' Owner '%s'.",
                        owner_partner.name, pet.name, pet.ths_pet_owner_id.name))

        elif pets and not owner_partner:
            # Try to determine owner from pets
            unique_owners = pets.mapped('ths_pet_owner_id')
            if len(set(unique_owners.ids)) == 1:
                owner_partner = unique_owners
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