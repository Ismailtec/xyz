# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError

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
        readonly=False,
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
            # AUTO-SELECT SINGLE PET
            if len(pets) == 1:
                self.ths_patient_ids = [Command.set([pets[0].id])]
                self.partner_ids = [Command.set([self.ths_pet_owner_id.id, pets[0].id])]

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

    @api.onchange('user_id')
    def _onchange_user_id_preserve_partners(self):
        """Prevent user_id changes from overriding our partner_ids"""
        # If we have vet-specific data, don't let user_id change partner_ids
        if self.ths_pet_owner_id or self.ths_patient_ids:
            # Rebuild partner_ids from our vet data
            partner_ids = []
            if self.ths_pet_owner_id:
                partner_ids.append(self.ths_pet_owner_id.id)
            if self.ths_patient_ids:
                partner_ids.extend(self.ths_patient_ids.ids)

            if partner_ids:
                self.partner_ids = [Command.set(partner_ids)]

    # --- CREATE/WRITE ---
    @api.model_create_multi
    def create(self, vals_list):
        """ handle walk-in and basic vet relationships """
        processed_vals_list = []
        for vals in vals_list:
            # Handle walk-in
            vals = self._handle_walkin_partner(vals.copy())

            # Auto-assign sequence
            vals["name"] = self.env["ir.sequence"].next_by_code("medical.appointment")

            processed_vals_list.append(vals)

        return super().create(processed_vals_list)

    def write(self, vals):
        """ handle walk-in """
        # Handle walk-in before super
        if vals.get("ths_is_walk_in") and not vals.get("ths_patient_ids") and not self.ths_patient_ids:
            vals = self._handle_walkin_partner(vals.copy())

        if hasattr(self, 'ths_pet_owner_id'):  # Only log for vet records
            _logger.warning(f"VET write() called with vals: {vals.keys()}")
            if 'partner_ids' in vals:
                _logger.warning(f"VET partner_ids being changed to: {vals['partner_ids']}")
            else:
                _logger.warning(
                    f"VET partner_ids NOT in vals - current partner_ids: {self.partner_ids.ids if self.partner_ids else 'None'}")

        # if 'ths_pet_owner_id' not in vals:
        #     # Ensure pet owner is set if pets are selected
        #     if self.ths_patient_ids and not self.ths_pet_owner_id:
        #         # Auto-set owner based on pets
        #         pet_owners = self.ths_patient_ids.mapped('ths_pet_owner_id')
        #         if len(set(pet_owners.ids)) == 1:
        #             vals['ths_pet_owner_id'] = pet_owners[0].id
        #         else:
        #             raise UserError(_("Multiple pet owners found. Please select a Pet Owner."))

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
        # context_partner_ids = self.env.context.get('default_partner_ids') or []
        # if context_partner_ids:
        #     partners = self.env['res.partner'].browse(context_partner_ids)
        #
        #     # Separate pets and owners
        #     pets = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet')
        #     owners = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet Owner')

        # if pets and 'ths_patient_ids' in fields_list:
        #     res['ths_patient_ids'] = [Command.set(pets.ids)]
        #
        #     # Auto-set owner if pets have common owner
        #     pet_owners = pets.mapped('ths_pet_owner_id')
        #     if len(set(pet_owners.ids)) == 1:
        #         owner = pet_owners[0]
        #         if 'ths_pet_owner_id' in fields_list:
        #             res['ths_pet_owner_id'] = owner.id
        #
        # elif owners and 'ths_pet_owner_id' in fields_list:
        #     # Owner selected directly
        #     res['ths_pet_owner_id'] = owners[0].id

        return res

    # --- VET-SPECIFIC CONSTRAINTS ---

    # --- ENCOUNTER CREATION FOR VET ---
    def _find_or_create_encounter(self):
        """Override for vet-specific encounter creation"""
        self.ensure_one()

        # Get pet owner (billing partner) for encounter lookup
        owner = self.ths_pet_owner_id
        pets = self.ths_patient_ids

        if not owner:
            raise UserError(_("Cannot create encounter: Pet Owner must be set."))
        if not pets:
            raise UserError(_("Cannot create encounter: Pets must be selected."))

        # Find or create daily encounter using pet owner
        encounter_date = self.start.date() if self.start else fields.Date.context_today(self)
        encounter = self.env['ths.medical.base.encounter']._find_or_create_daily_encounter(
            owner.id, encounter_date
        )

        # Link appointment to encounter
        self.encounter_id = encounter.id

        # Ensure vet-specific fields are set
        if not encounter.ths_pet_owner_id:
            encounter.ths_pet_owner_id = owner.id

        # Add pets to encounter if not already present
        existing_patients = encounter.patient_ids
        new_patients = pets - existing_patients
        if new_patients:
            encounter.patient_ids = [Command.link(p.id) for p in new_patients]

        return encounter

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

# TODO: Add multi-pet appointment splitting into separate encounters
# TODO: Implement pet-specific appointment templates
# TODO: Add appointment breed/species validation
# TODO: Implement pet availability checking for boarding integration
