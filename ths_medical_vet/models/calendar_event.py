# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # Override ths_patient_ids for vet context - now refers to pets
    ths_patient_ids = fields.Many2many(
        'res.partner',
        'calendar_event_patient_rel',  # Use same relation table as base
        'event_id',
        'patient_id',
        string='Pets',  # Relabeled for veterinary context
        domain="[('ths_partner_type_id.name', '=', 'Pet')]",  # Filter for pets only
        store=True,
        index=True,
        tracking=True,
        help="Pets attending this appointment and receiving veterinary care."
    )

    # Pet Owner field - the billing customer in vet practice
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        domain="[('ths_partner_type_id.name','=','Pet Owner')]",
        store=True,
        readonly=False,
        index=True,
        tracking=True,
        help="Pet owner responsible for payment. Select this first to filter available pets.",
    )

    # Computed domain string for pets based on selected owner
    ths_patient_ids_domain = fields.Char(
        compute='_compute_patient_domain',
        store=False
    )

    # --- CORE LOGIC: POPULATE partner_ids BASED ON VET FIELDS ---

    @api.depends('ths_pet_owner_id')
    def _compute_patient_domain(self):
        """Compute domain for pets based on selected owner"""
        for rec in self:
            if rec.ths_pet_owner_id:
                # Filter pets by selected owner
                rec.ths_patient_ids_domain = str([
                    ('ths_pet_owner_id', '=', rec.ths_pet_owner_id.id),
                    ('ths_partner_type_id.name', '=', 'Pet')
                ])
            else:
                # Show all pets when no owner selected
                rec.ths_patient_ids_domain = str([('ths_partner_type_id.name', '=', 'Pet')])

    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_populate_partners(self):
        """
        CORE METHOD: When pet owner changes, populate partner_ids and filter pets
        This is the main method that controls the partner_ids field
        """
        # Clear pets when owner changes
        self.ths_patient_ids = [Command.clear()]

        # Populate partner_ids with pet owner only
        if self.ths_pet_owner_id:
            self.partner_ids = [Command.set([self.ths_pet_owner_id.id])]

            # Set domain for pets
            pets = self.env['res.partner'].search([
                ('ths_partner_type_id.name', '=', 'Pet'),
                ('ths_pet_owner_id', '=', self.ths_pet_owner_id.id)
            ])

            return {
                'domain': {
                    'ths_patient_ids': [('id', 'in', pets.ids)] if pets else [('id', '=', False)]
                }
            }
        else:
            # Clear partner_ids when no owner
            self.partner_ids = [Command.clear()]

            return {
                'domain': {
                    'ths_patient_ids': [('ths_partner_type_id.name', '=', 'Pet')]
                }
            }

    @api.onchange('ths_patient_ids')
    def _onchange_pets_add_to_partners(self):
        """
        CORE METHOD: When pets change, add them to partner_ids (keeping owner)
        """
        if not self.ths_pet_owner_id:
            # No owner selected - show warning and clear pets
            if self.ths_patient_ids:
                self.ths_patient_ids = [Command.clear()]
                return {
                    'warning': {
                        'title': _('Select Pet Owner First'),
                        'message': _('Please select a Pet Owner before selecting pets.')
                    }
                }
            return None

        # Build partner_ids: owner + selected pets
        partner_ids = [self.ths_pet_owner_id.id]
        if self.ths_patient_ids:
            # Check if all pets belong to the selected owner
            # wrong_owner_pets = self.ths_patient_ids.filtered(
            #     lambda p: p.ths_pet_owner_id != self.ths_pet_owner_id
            # )
            # if wrong_owner_pets:
            #     # Remove pets that don't belong to the selected owner
            #     correct_pets = self.ths_patient_ids - wrong_owner_pets
            #     self.ths_patient_ids = [Command.set(correct_pets.ids)]
            #
            #     return {
            #         'warning': {
            #             'title': _('Pet Owner Mismatch'),
            #             'message': _(
            #                 'Some pets were removed because they belong to different owners: %s',
            #                 ', '.join(wrong_owner_pets.mapped('name'))
            #             )
            #         }
            #     }

            partner_ids.extend(self.ths_patient_ids.ids)

        # Update partner_ids with owner + pets
        self.partner_ids = [Command.set(partner_ids)]
        return None

    # --- SIMPLIFIED CREATE/WRITE ---

    @api.model_create_multi
    def create(self, vals_list):
        """Simplified create - handle walk-in and basic vet relationships"""
        processed_vals_list = []
        for vals in vals_list:
            # Handle walk-in
            vals = self._handle_walkin_partner(vals.copy())

            # Auto-assign sequence
            vals["name"] = self.env["ir.sequence"].next_by_code("medical.appointment")

            processed_vals_list.append(vals)

        return super().create(processed_vals_list)

    def write(self, vals):
        """Simplified write - handle walk-in"""
        # Handle walk-in before super
        if vals.get("ths_is_walk_in") and not vals.get("ths_patient_ids") and not self.ths_patient_ids:
            vals = self._handle_walkin_partner(vals.copy())

        return super().write(vals)

    # --- SIMPLIFIED DEFAULT_GET ---

    @api.model
    def default_get(self, fields_list):
        """Simplified default_get - let onchange methods handle the relationships"""
        res = super().default_get(fields_list)

        # Set default medical status
        if res.get('appointment_type_id') and 'appointment_status' in fields_list and not res.get('appointment_status'):
            res['appointment_status'] = 'draft'

        # Handle context with specific vet partners
        context_partner_ids = self.env.context.get('default_partner_ids') or []
        if context_partner_ids:
            partners = self.env['res.partner'].browse(context_partner_ids)

            # Separate pets and owners
            pets = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet')
            owners = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet Owner')

            if pets and 'ths_patient_ids' in fields_list:
                res['ths_patient_ids'] = [Command.set(pets.ids)]

                # Auto-set owner if pets have common owner
                pet_owners = pets.mapped('ths_pet_owner_id')
                if len(set(pet_owners.ids)) == 1:
                    owner = pet_owners[0]
                    if 'ths_pet_owner_id' in fields_list:
                        res['ths_pet_owner_id'] = owner.id

            elif owners and 'ths_pet_owner_id' in fields_list:
                # Owner selected directly
                res['ths_pet_owner_id'] = owners[0].id

        return res

    # --- VET-SPECIFIC CONSTRAINTS ---


    # --- ENCOUNTER CREATION FOR VET ---

    def _prepare_encounter_vals(self):
        """
        Override to use ths_pet_owner_id for billing (partner_id) in encounter
        This allows encounter to have proper billing customer without maintaining partner_id in appointment
        """
        self.ensure_one()
        pets = self.ths_patient_ids
        owner = self.ths_pet_owner_id

        # Validate vet-specific requirements
        if not pets:
            raise UserError(_("Cannot create encounter: No pets selected for the appointment."))

        if not owner:
            raise UserError(_("Cannot create encounter: Pet Owner is not set."))

        if not self.ths_practitioner_id:
            raise UserError(_("Cannot create encounter: Practitioner is not set on the appointment."))

        return {
            'appointment_id': self.id,
            'state': 'draft',
            'patient_ids': [Command.set(pets.ids)],  # Pets receiving care
            'practitioner_id': self.ths_practitioner_id.id,
            'partner_id': owner.id,  # Pet owner for billing (from ths_pet_owner_id)
            'chief_complaint': self.ths_reason_for_visit,
        }

    # --- HELPER METHODS ---

    def _get_primary_pet(self):
        """Get the primary/first pet for this appointment"""
        self.ensure_one()
        return self.ths_patient_ids[0] if self.ths_patient_ids else False

    def _get_all_pets_species(self):
        """Get unique species of all pets in this appointment"""
        self.ensure_one()
        return self.ths_patient_ids.mapped('ths_species_id').mapped('name')

    # TODO: Add methods for vet-specific appointment workflows
    def action_create_vaccination_reminders(self):
        """Create vaccination reminders for pets in this appointment"""
        # TODO: Implement vaccination reminder system
        pass

    def action_create_boarding_request(self):
        """Create boarding request for pets if needed"""
        # TODO: Implement boarding integration
        pass

    def action_schedule_follow_up(self):
        """Schedule follow-up appointment for pets"""
        # TODO: Implement follow-up scheduling
        pass
