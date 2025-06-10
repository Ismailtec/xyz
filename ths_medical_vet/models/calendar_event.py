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
        compute='_compute_patient_ids',
        inverse='_inverse_patient_ids',
        domain="[('ths_partner_type_id.name', '=', 'Pet')]",  # Filter for pets only
        store=True,
        index=True,
        tracking=True,
        help="Pets attending this appointment and receiving veterinary care."
    )

    # Keep Pet Owner field, synced with partner_id for vet billing
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        compute='_compute_pet_owner',
        inverse='_inverse_pet_owner',
        domain="[('ths_partner_type_id.name','=','Pet Owner')]",
        store=True,
        readonly=False,
        index=True,
        help="Pet owner responsible for payment. This is synced with the appointment's main customer.",
    )

    # Computed domain string for pets based on selected owner
    ths_patient_ids_domain = fields.Char(
        compute='_compute_patient_domain',
        store=False
    )

    # --- VET-SPECIFIC COMPUTE METHODS ---

    @api.depends('partner_ids')
    def _compute_patient_ids(self):
        """
        For vet practice: extract pets from partner_ids
        partner_ids should contain: [Pet Owner] + [Pet1, Pet2, ...]
        """
        for rec in self:
            if rec.partner_ids:
                # Filter only pets from partner_ids
                pets = rec.partner_ids.filtered(
                    lambda p: p.ths_partner_type_id.name == 'Pet')
                rec.ths_patient_ids = [Command.set(pets.ids)] if pets else [Command.clear()]
            else:
                rec.ths_patient_ids = [Command.clear()]

    def _inverse_patient_ids(self):
        """
        For vet practice: when pets change, update partner_ids to include pets + owner
        """
        for rec in self:
            partner_ids = []

            # Add selected pets
            if rec.ths_patient_ids:
                partner_ids.extend(rec.ths_patient_ids.ids)

            # Add pet owner (from partner_id or ths_pet_owner_id)
            owner = rec.partner_id or rec.ths_pet_owner_id
            if owner and owner.id not in partner_ids:
                partner_ids.append(owner.id)

            rec.partner_ids = [Command.set(partner_ids)] if partner_ids else [Command.clear()]

    @api.depends('partner_id')
    def _compute_pet_owner(self):
        """
        For vet practice: sync ths_pet_owner_id with partner_id
        In vet context, partner_id should always be the pet owner (billing customer)
        """
        for rec in self:
            rec.ths_pet_owner_id = rec.partner_id

    def _inverse_pet_owner(self):
        """
        For vet practice: when pet owner changes, update partner_id (billing customer)
        """
        for rec in self:
            if rec.ths_pet_owner_id:
                rec.partner_id = rec.ths_pet_owner_id
                # Trigger partner_ids update to include owner + pets
                rec._inverse_patient_ids()

    @api.depends('ths_pet_owner_id')
    def _compute_patient_domain(self):
        """
        Compute domain for pets based on selected owner
        """
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

    # --- VET-SPECIFIC ONCHANGE METHODS ---

    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_filter_pets(self):
        """
        When owner changes, filter available pets and update billing customer
        """
        if self.ths_pet_owner_id:
            # Set as main billing customer
            self.partner_id = self.ths_pet_owner_id

            # Find pets for this owner
            pets = self.env['res.partner'].search([
                ('ths_partner_type_id.name', '=', 'Pet'),
                ('ths_pet_owner_id', '=', self.ths_pet_owner_id.id)
            ])

            # Clear current pet selection - user will reselect appropriate pets
            self.ths_patient_ids = [Command.clear()]

            # Update domain to show only this owner's pets
            return {
                'domain': {
                    'ths_patient_ids': [('id', 'in', pets.ids)] if pets else [('id', '=', False)]
                }
            }
        else:
            # Clear billing customer if no owner
            self.partner_id = False
            # Show all pets when no owner selected
            return {
                'domain': {
                    'ths_patient_ids': [('ths_partner_type_id.name', '=', 'Pet')]
                }
            }

    @api.onchange('ths_patient_ids')
    def _onchange_patient_sync_owner(self):
        """
        When pets are selected, auto-set owner if all pets have same owner
        """
        if self.ths_patient_ids:
            owners = self.ths_patient_ids.mapped('ths_pet_owner_id')
            unique_owners = list(set(owners.ids)) if owners else []

            if len(unique_owners) == 1:
                # All pets have same owner - auto-set it
                self.ths_pet_owner_id = owners[0]
                self.partner_id = owners[0]  # Set as billing customer
            elif len(unique_owners) > 1:
                # Multiple owners - show warning and require manual selection
                # TODO: Could show warning message about multiple owners
                return {
                    'warning': {
                        'title': _('Multiple Pet Owners'),
                        'message': _(
                            'Selected pets belong to different owners. Please select pets from the same owner or choose the primary owner for billing.')
                    }
                }

    @api.onchange('partner_ids')
    def _onchange_partner_ids_extract_owner_and_pets(self):
        """
        Extract pet owner and pets from partner_ids when manually changed
        """
        if self.partner_ids:
            # Look for pet owners in partner_ids
            owners = self.partner_ids.filtered(
                lambda p: p.ths_partner_type_id.name == 'Pet Owner')
            pets = self.partner_ids.filtered(
                lambda p: p.ths_partner_type_id.name == 'Pet')

            # Set primary owner (first one found)
            if owners and not self.ths_pet_owner_id:
                self.ths_pet_owner_id = owners[0]
                self.partner_id = owners[0]  # Set as billing customer

            # Set pets
            if pets:
                self.ths_patient_ids = [Command.set(pets.ids)]

    @api.onchange('partner_id')
    def _onchange_partner_id_sync_owner(self):
        """
        When partner_id changes, sync with ths_pet_owner_id
        """
        if self.partner_id and self.partner_id != self.ths_pet_owner_id:
            # Check if partner_id is a valid pet owner
            if self.partner_id.ths_partner_type_id.name == 'Pet Owner':
                self.ths_pet_owner_id = self.partner_id
            elif self.partner_id.ths_partner_type_id.name == 'Pet':
                # If a pet is selected as partner_id, get its owner
                if self.partner_id.ths_pet_owner_id:
                    self.ths_pet_owner_id = self.partner_id.ths_pet_owner_id
                    self.partner_id = self.partner_id.ths_pet_owner_id  # Set owner as billing customer

    # --- OVERRIDE DEFAULT_GET ---
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Handle default partner_ids for Many2many field in vet context
        partner_ids = self.env.context.get('default_partner_ids') or []
        if partner_ids:
            partners = self.env['res.partner'].browse(partner_ids)

            # Separate pets and owners
            pets = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet')
            owners = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet Owner')

            if pets and 'ths_patient_ids' in fields_list:
                res['ths_patient_ids'] = [Command.set(pets.ids)]

                # Auto-set owner if pets have common owner
                pet_owners = pets.mapped('ths_pet_owner_id')
                if len(set(pet_owners.ids)) == 1 and 'ths_pet_owner_id' in fields_list:
                    res['ths_pet_owner_id'] = pet_owners[0].id
                    res['partner_ids'] = pet_owners[0].id  # Set as billing customer

            elif owners and 'ths_pet_owner_id' in fields_list:
                # Owner selected directly
                res['ths_pet_owner_id'] = owners[0].id
                res['partner_ids'] = owners[0].id  # Set as billing customer

        return res

    # --- OVERRIDE CREATE/WRITE ---
    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to handle vet-specific partner/patient relationships
        """
        processed_vals_list = []
        for vals in vals_list:
            vals = self._handle_walkin_partner(vals.copy())

            # For vet practice: ensure proper owner/pet relationships
            if vals.get('ths_pet_owner_id') and not vals.get('partner_id'):
                # Set pet owner as billing customer
                vals['partner_id'] = vals['ths_pet_owner_id']

            if vals.get('partner_id') and not vals.get('ths_pet_owner_id'):
                # Sync owner field with billing customer
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.ths_partner_type_id.name == 'Pet Owner':
                    vals['ths_pet_owner_id'] = vals['partner_id']
                elif partner.ths_partner_type_id.name == 'Pet' and partner.ths_pet_owner_id:
                    # If pet selected as partner, use its owner
                    vals['ths_pet_owner_id'] = partner.ths_pet_owner_id.id
                    vals['partner_id'] = partner.ths_pet_owner_id.id

            # Handle partner_ids to include both owner and pets
            if vals.get('ths_patient_ids') or vals.get('partner_id'):
                partner_ids = []

                # Add billing customer (pet owner)
                if vals.get('partner_id'):
                    partner_ids.append(vals['partner_id'])

                # Add pets from ths_patient_ids
                if vals.get('ths_patient_ids'):
                    for cmd in vals['ths_patient_ids']:
                        if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == Command.SET:
                            partner_ids.extend(cmd[2] if cmd[2] else [])

                if partner_ids and 'partner_ids' not in vals:
                    vals['partner_ids'] = [Command.set(list(set(partner_ids)))]

            vals["name"] = self.env["ir.sequence"].next_by_code("medical.appointment")
            processed_vals_list.append(vals)

        return super().create(processed_vals_list)

    def write(self, vals):
        """
        Override write to maintain vet-specific relationships
        """
        # Handle walk-in before super
        if vals.get("ths_is_walk_in") and not vals.get("ths_patient_ids") and not self.ths_patient_ids:
            vals = self._handle_walkin_partner(vals.copy())

        # For vet practice: maintain partner_id = pet owner relationship
        if 'ths_pet_owner_id' in vals and 'partner_id' not in vals:
            vals['partner_id'] = vals['ths_pet_owner_id']

        if 'partner_id' in vals and 'ths_pet_owner_id' not in vals:
            # Ensure partner_id is always a pet owner
            if vals['partner_id']:
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.ths_partner_type_id.name == 'Pet Owner':
                    vals['ths_pet_owner_id'] = vals['partner_id']
                elif partner.ths_partner_type_id.name == 'Pet' and partner.ths_pet_owner_id:
                    vals['ths_pet_owner_id'] = partner.ths_pet_owner_id.id
                    vals['partner_id'] = partner.ths_pet_owner_id.id

        # Handle partner_ids updates to include owner + pets
        if 'ths_patient_ids' in vals or 'partner_id' in vals:
            partner_ids = []

            # Add current or new billing customer
            billing_customer = vals.get('partner_id') or self.partner_id.id if self.partner_id else None
            if billing_customer:
                partner_ids.append(billing_customer)

            # Add current or new pets
            if 'ths_patient_ids' in vals:
                for cmd in vals['ths_patient_ids']:
                    if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == Command.SET:
                        partner_ids.extend(cmd[2] if cmd[2] else [])
            else:
                # Keep existing pets
                partner_ids.extend(self.ths_patient_ids.ids)

            if 'partner_ids' not in vals and partner_ids:
                vals['partner_ids'] = [Command.set(list(set(partner_ids)))]

        return super().write(vals)

    # --- OVERRIDE ENCOUNTER CREATION FOR VET ---
    def _prepare_encounter_vals(self):
        """
        Override to ensure Pets -> patient_ids, Pet Owner -> partner_id for vet practice
        """
        self.ensure_one()
        pets = self.ths_patient_ids
        owner_partner = self.ths_pet_owner_id or self.partner_id

        # Validate vet-specific requirements
        if not pets:
            raise UserError(_("Cannot create encounter: No pets selected for the appointment."))

        if not owner_partner:
            raise UserError(_("Cannot create encounter: Pet Owner (billing customer) is not set."))

        # Validate pet ownership consistency
        for pet in pets:
            if pet.ths_pet_owner_id and pet.ths_pet_owner_id != owner_partner:
                raise UserError(_(
                    "Consistency Error: Pet '%s' belongs to owner '%s', but appointment is for owner '%s'.",
                    pet.name, pet.ths_pet_owner_id.name, owner_partner.name))

        if not self.ths_practitioner_id:
            raise UserError(_("Cannot create encounter: Practitioner is not set on the appointment."))

        return {
            'appointment_id': self.id,
            'state': 'draft',
            'patient_ids': [Command.set(pets.ids)],  # Pets receiving care
            'practitioner_id': self.ths_practitioner_id.id,
            'partner_id': owner_partner.id,  # Pet owner responsible for billing
            'chief_complaint': self.ths_reason_for_visit,
        }

    # --- VET-SPECIFIC CONSTRAINT VALIDATIONS ---
    @api.constrains('ths_patient_ids', 'ths_pet_owner_id', 'partner_id')
    def _check_vet_appointment_consistency(self):
        """
        Validate vet appointment consistency:
        1. All pets must belong to the same owner
        2. partner_id must be the pet owner (billing customer)
        3. ths_pet_owner_id must match partner_id
        """
        for appointment in self:
            if appointment.ths_patient_ids:
                # Check 1: All pets must have the same owner
                pet_owners = appointment.ths_patient_ids.mapped('ths_pet_owner_id')
                unique_owners = list(set(pet_owners.ids)) if pet_owners else []

                if len(unique_owners) > 1:
                    owner_names = [owner.name for owner in pet_owners if owner]
                    raise UserError(_(
                        "All pets in an appointment must belong to the same owner. "
                        "Found pets belonging to: %s", ', '.join(set(owner_names))
                    ))

                # Check 2 & 3: Owner consistency with billing
                if unique_owners and appointment.partner_id:
                    expected_owner_id = unique_owners[0]
                    if appointment.partner_id.id != expected_owner_id:
                        expected_owner = self.env['res.partner'].browse(expected_owner_id)
                        raise UserError(_(
                            "Billing customer must be the pet owner. "
                            "Expected: %s, Current: %s",
                            expected_owner.name, appointment.partner_id.name
                        ))

                if appointment.ths_pet_owner_id and appointment.partner_id:
                    if appointment.ths_pet_owner_id != appointment.partner_id:
                        raise UserError(_(
                            "Pet Owner field must match the billing customer. "
                            "Pet Owner: %s, Billing Customer: %s",
                            appointment.ths_pet_owner_id.name, appointment.partner_id.name
                        ))

    # TODO: Add vet-specific helper methods
    def _get_primary_pet(self):
        """Get the primary/first pet for this appointment"""
        self.ensure_one()
        return self.ths_patient_ids[0] if self.ths_patient_ids else False

    def _get_all_pets_species(self):
        """Get unique species of all pets in this appointment"""
        self.ensure_one()
        return self.ths_patient_ids.mapped('ths_species_id').mapped('name')

    # TODO: Add methods for vet-specific appointment workflows
    # def action_create_vaccination_reminders(self):
    #     """Create vaccination reminders for pets in this appointment"""
    #     pass
    #
    # def action_create_boarding_request(self):
    #     """Create boarding request for pets if needed"""
    #     pass