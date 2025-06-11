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

    # Pet Owner field - synced with partner_id for vet billing
    # FIXED: Removed automatic compute to prevent auto-selection issue
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        domain="[('ths_partner_type_id.name','=','Pet Owner')]",
        store=True,
        readonly=False,
        index=True,
        tracking=True,
        help="Pet owner responsible for payment. This should be selected manually and will become the billing customer.",
    )

    # Computed domain string for pets based on selected owner
    ths_patient_ids_domain = fields.Char(
        compute='_compute_patient_domain',
        store=False
    )

    # --- FIXED COMPUTE METHODS ---

    @api.depends('partner_ids')
    def _compute_patient_ids(self):
        """
        For vet practice: extract pets from partner_ids
        partner_ids should contain: [Pet Owner] + [Pet1, Pet2, ...]
        FIXED: More conservative approach to work with appointment module logic
        """
        for rec in self:
            if rec.partner_ids:
                # Filter only pets from partner_ids
                pets = rec.partner_ids.filtered(
                    lambda p: p.ths_partner_type_id.name == 'Pet')
                if pets:
                    # Only update if different to avoid triggering cascading updates
                    if set(pets.ids) != set(rec.ths_patient_ids.ids):
                        rec.ths_patient_ids = [Command.set(pets.ids)]
                else:
                    if rec.ths_patient_ids:
                        rec.ths_patient_ids = [Command.clear()]
            else:
                if rec.ths_patient_ids:
                    rec.ths_patient_ids = [Command.clear()]

    def _inverse_patient_ids(self):
        """
        For vet practice: when pets change, update partner_ids to include pets + owner
        FIXED: Work with appointment module's partner_ids logic
        """
        for rec in self:
            # Build new partner_ids list
            new_partner_ids = []

            # Add selected pets first
            if rec.ths_patient_ids:
                new_partner_ids.extend(rec.ths_patient_ids.ids)

            # Add pet owner if explicitly set
            if rec.ths_pet_owner_id:
                if rec.ths_pet_owner_id.id not in new_partner_ids:
                    new_partner_ids.append(rec.ths_pet_owner_id.id)

                # Update partner_id to match pet owner (for billing)
                if rec.partner_id != rec.ths_pet_owner_id:
                    rec.partner_id = rec.ths_pet_owner_id

            # Only update partner_ids if different to avoid cascading updates
            if new_partner_ids and set(new_partner_ids) != set(rec.partner_ids.ids):
                rec.partner_ids = [Command.set(new_partner_ids)]
            elif not new_partner_ids and rec.partner_ids:
                rec.partner_ids = [Command.clear()]

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

    # --- FIXED ONCHANGE METHODS ---

    @api.onchange('ths_pet_owner_id')
    def _onchange_pet_owner_filter_pets(self):
        """
        When owner changes, filter available pets and update billing customer
        FIXED: Improved logic to prevent circular updates
        """
        if self.ths_pet_owner_id:
            # Set as main billing customer ONLY if not already set or different
            if self.partner_id != self.ths_pet_owner_id:
                self.partner_id = self.ths_pet_owner_id

            # Find pets for this owner
            pets = self.env['res.partner'].search([
                ('ths_partner_type_id.name', '=', 'Pet'),
                ('ths_pet_owner_id', '=', self.ths_pet_owner_id.id)
            ])

            # Clear current pet selection - user will reselect appropriate pets
            self.ths_patient_ids = [Command.clear()]

            # Return domain to show only this owner's pets
            return {
                'domain': {
                    'ths_patient_ids': [('id', 'in', pets.ids)] if pets else [('id', '=', False)]
                }
            }
        else:
            # FIXED: Don't automatically clear partner_id when pet owner is cleared
            # Let user manage partner_id manually
            # Show all pets when no owner selected
            return {
                'domain': {
                    'ths_patient_ids': [('ths_partner_type_id.name', '=', 'Pet')]
                }
            }

    @api.onchange('ths_patient_ids')
    def _onchange_patient_sync_owner(self):
        """
        When pets are selected, suggest owner if all pets have same owner
        FIXED: Only suggest, don't automatically set to prevent forced updates
        """
        if self.ths_patient_ids:
            owners = self.ths_patient_ids.mapped('ths_pet_owner_id')
            unique_owners = list(set(owners.ids)) if owners else []

            if len(unique_owners) == 1 and not self.ths_pet_owner_id:
                # Auto-set owner only if none is currently selected
                self.ths_pet_owner_id = owners[0]
                self.partner_id = owners[0]  # Set as billing customer
            elif len(unique_owners) > 1:
                # Multiple owners - show warning and require manual selection
                return {
                    'warning': {
                        'title': _('Multiple Pet Owners'),
                        'message': _(
                            'Selected pets belong to different owners. Please select pets from the same owner or choose the primary owner for billing.')
                    }
                }
            # If owner already selected, don't change it

    @api.onchange('partner_ids')
    def _onchange_partner_ids_extract_owner_and_pets(self):
        """
        Extract pet owner and pets from partner_ids when manually changed
        FIXED: More conservative to prevent unwanted auto-updates
        """
        if self.partner_ids:
            # Look for pet owners in partner_ids
            owners = self.partner_ids.filtered(
                lambda p: p.ths_partner_type_id.name == 'Pet Owner')
            pets = self.partner_ids.filtered(
                lambda p: p.ths_partner_type_id.name == 'Pet')

            # Set primary owner ONLY if not already set
            if owners and not self.ths_pet_owner_id:
                self.ths_pet_owner_id = owners[0]
                # Ensure partner_id is set to this owner
                if self.partner_id != owners[0]:
                    self.partner_id = owners[0]

            # Set pets
            if pets:
                self.ths_patient_ids = [Command.set(pets.ids)]

    @api.onchange('partner_id')
    def _onchange_partner_id_sync_owner(self):
        """
        When partner_id changes, sync with ths_pet_owner_id if it's a valid pet owner
        FIXED: Only sync if partner_id is a valid pet owner, prevent unwanted auto-updates
        """
        if self.partner_id:
            # Only sync if partner_id is a Pet Owner and different from current pet owner
            if (self.partner_id.ths_partner_type_id.name == 'Pet Owner' and
                    self.partner_id != self.ths_pet_owner_id):
                self.ths_pet_owner_id = self.partner_id
            elif self.partner_id.ths_partner_type_id.name == 'Pet':
                # If a pet is selected as partner_id, get its owner but show warning
                if self.partner_id.ths_pet_owner_id:
                    self.ths_pet_owner_id = self.partner_id.ths_pet_owner_id
                    self.partner_id = self.partner_id.ths_pet_owner_id  # Set owner as billing customer
                    return {
                        'warning': {
                            'title': _('Pet Selected as Customer'),
                            'message': _(
                                'A pet was selected as customer. The billing customer has been changed to the pet owner: %s',
                                self.ths_pet_owner_id.name)
                        }
                    }

        # FIXED: Explicit return for PyCharm warning
        return None

    # --- OVERRIDE DEFAULT_GET TO PREVENT AUTO-POPULATION ---
    @api.model
    def default_get(self, fields_list):
        # CRITICAL: Call parent default_get first to get appointment module logic
        res = super().default_get(fields_list)

        # FIXED: Handle appointment module's auto-population of partner_ids and partner_id
        # The appointment module sets partner_ids first, then computes partner_id from it

        # 1. Remove current user auto-population from partner_ids if it exists
        if 'partner_ids' in res and res.get('partner_ids'):
            # Check if partner_ids contains current user (Administrator issue)
            current_user_partner = self.env.user.partner_id
            partner_commands = res['partner_ids']

            # Extract partner IDs from Command operations
            auto_populated_ids = []
            if isinstance(partner_commands, list):
                for cmd in partner_commands:
                    if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == Command.SET:
                        auto_populated_ids.extend(cmd[2] if cmd[2] else [])

            # Remove current user if auto-populated
            if current_user_partner.id in auto_populated_ids:
                _logger.info(f"VET: Removed current user {current_user_partner.name} from auto-populated partner_ids")
                auto_populated_ids.remove(current_user_partner.id)
                if auto_populated_ids:
                    res['partner_ids'] = [Command.set(auto_populated_ids)]
                else:
                    res['partner_ids'] = [Command.clear()]

        # 2. Remove current user auto-population from partner_id if it exists
        if 'partner_id' in res and res.get('partner_id'):
            partner = self.env['res.partner'].browse(res['partner_id'])
            if partner.user_ids and self.env.user in partner.user_ids:
                _logger.info(f"VET: Removed auto-populated partner_id {partner.name} (current user)")
                del res['partner_id']

        # 3. Handle vet-specific context with default partner_ids
        context_partner_ids = self.env.context.get('default_partner_ids') or []
        if context_partner_ids:
            partners = self.env['res.partner'].browse(context_partner_ids)

            # Separate pets and owners
            pets = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet')
            owners = partners.filtered(lambda p: p.ths_partner_type_id.name == 'Pet Owner')

            if pets and 'ths_patient_ids' in fields_list:
                res['ths_patient_ids'] = [Command.set(pets.ids)]

                # Set partner_ids to include pets
                res['partner_ids'] = [Command.set(pets.ids)]

                # Auto-set owner if pets have common owner
                pet_owners = pets.mapped('ths_pet_owner_id')
                if len(set(pet_owners.ids)) == 1:
                    owner = pet_owners[0]
                    if 'ths_pet_owner_id' in fields_list:
                        res['ths_pet_owner_id'] = owner.id
                    if 'partner_id' in fields_list:
                        res['partner_id'] = owner.id
                    # Add owner to partner_ids
                    if 'partner_ids' in fields_list:
                        res['partner_ids'] = [Command.set(pets.ids + [owner.id])]

            elif owners and 'ths_pet_owner_id' in fields_list:
                # Owner selected directly
                res['ths_pet_owner_id'] = owners[0].id
                if 'partner_id' in fields_list:
                    res['partner_id'] = owners[0].id
                if 'partner_ids' in fields_list:
                    res['partner_ids'] = [Command.set(owners.ids)]

        return res

    # --- OVERRIDE CREATE/WRITE FOR VET WORKFLOW ---
    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to handle vet-specific partner/patient relationships
        FIXED: Better handling to prevent unwanted auto-population
        """
        processed_vals_list = []
        for vals in vals_list:
            vals = self._handle_walkin_partner(vals.copy())

            # FIXED: Only sync fields if explicitly provided, don't auto-populate
            # For vet practice: ensure proper owner/pet relationships
            if vals.get('ths_pet_owner_id') and not vals.get('partner_id'):
                # Set pet owner as billing customer only if not already set
                vals['partner_id'] = vals['ths_pet_owner_id']

            # FIXED: Remove logic that auto-populates based on partner_id to prevent Administrator issue
            # Only sync if partner_id is explicitly a Pet Owner
            if vals.get('partner_id') and not vals.get('ths_pet_owner_id'):
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
        Override write to maintain vet-specific relationships and handle appointment module logic
        FIXED: Better handling of appointment module's partner_ids/partner_id logic
        """
        # Handle walk-in before super
        if vals.get("ths_is_walk_in") and not vals.get("ths_patient_ids") and not self.ths_patient_ids:
            vals = self._handle_walkin_partner(vals.copy())

        # FIXED: Detect and handle appointment module trying to set partner_id to current user
        if 'partner_id' in vals and vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            # If appointment module is trying to set current user as partner_id, intercept it
            if partner.user_ids and self.env.user in partner.user_ids:
                _logger.info(f"VET: Intercepted attempt to set partner_id to current user {partner.name}")
                # Don't set partner_id to current user in vet context
                # Keep existing pet owner if set, otherwise clear
                for rec in self:
                    if rec.ths_pet_owner_id:
                        vals['partner_id'] = rec.ths_pet_owner_id.id
                        break
                else:
                    # No pet owner set, remove the problematic partner_id
                    del vals['partner_id']

        # For vet practice: maintain partner_id = pet owner relationship
        # FIXED: Only update if explicitly provided and valid
        if 'ths_pet_owner_id' in vals and vals['ths_pet_owner_id']:
            if 'partner_id' not in vals:
                vals['partner_id'] = vals['ths_pet_owner_id']

        # FIXED: Only sync partner_id to ths_pet_owner_id if partner_id is explicitly a Pet Owner
        if 'partner_id' in vals and vals.get('partner_id') and 'ths_pet_owner_id' not in vals:
            partner = self.env['res.partner'].browse(vals['partner_id'])
            if partner.ths_partner_type_id.name == 'Pet Owner':
                vals['ths_pet_owner_id'] = vals['partner_id']
            elif partner.ths_partner_type_id.name == 'Pet' and partner.ths_pet_owner_id:
                # If pet selected as partner, use its owner
                vals['ths_pet_owner_id'] = partner.ths_pet_owner_id.id
                vals['partner_id'] = partner.ths_pet_owner_id.id

        # Handle partner_ids updates to include owner + pets
        # FIXED: Only update if explicitly changing vet-related fields
        if 'ths_patient_ids' in vals or ('ths_pet_owner_id' in vals and vals.get('ths_pet_owner_id')):
            partner_ids = []

            # Add current or new billing customer (pet owner)
            billing_customer = vals.get('partner_id')
            if not billing_customer:
                # Use ths_pet_owner_id if partner_id not in vals
                billing_customer = vals.get('ths_pet_owner_id')
                if not billing_customer:
                    # Fall back to existing values
                    for rec in self:
                        billing_customer = rec.ths_pet_owner_id.id if rec.ths_pet_owner_id else rec.partner_id.id
                        break

            if billing_customer:
                partner_ids.append(billing_customer)

            # Add current or new pets
            if 'ths_patient_ids' in vals:
                for cmd in vals['ths_patient_ids']:
                    if isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == Command.SET:
                        partner_ids.extend(cmd[2] if cmd[2] else [])
            else:
                # Keep existing pets
                for rec in self:
                    partner_ids.extend(rec.ths_patient_ids.ids)
                    break

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
