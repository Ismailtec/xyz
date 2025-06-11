# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

import logging

_logger = logging.getLogger(__name__)


class ThsPendingPosItem(models.Model):
    _inherit = 'ths.pending.pos.item'

    # Override partner_id to ensure it refers to Pet Owner (billing customer)
    partner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner (Billing)',
        domain="[('ths_partner_type_id.name', '=', 'Pet Owner')]",
        required=True,
        index=True,
        tracking=True,
        help="Pet owner who will be billed for this service. This is the billing customer in veterinary practice."
    )

    # Override patient_id to ensure it refers to individual pet receiving service
    patient_id = fields.Many2one(
        'res.partner',
        string='Pet (Patient)',
        domain="[('ths_partner_type_id.name', '=', 'Pet')]",
        required=True,
        index=True,
        tracking=True,
        help="Individual pet receiving this service. This is the actual patient in veterinary practice."
    )

    # Add Pet Owner relationship field for better UX
    ths_pet_owner_id = fields.Many2one(
        'res.partner',
        string='Pet Owner',
        related='partner_id',
        store=True,
        readonly=True,
        help="Pet owner responsible for billing (same as partner_id in vet context)."
    )

    # Add computed domain for patient selection based on owner
    patient_id_domain = fields.Char(
        compute='_compute_patient_domain',
        store=False
    )

    # Add pet species and breed for better identification
    pet_species_id = fields.Many2one(
        'ths.species',
        string='Pet Species',
        related='patient_id.ths_species_id',
        store=True,
        readonly=True,
        help="Species of the pet receiving this service."
    )

    pet_breed_id = fields.Many2one(
        'ths.breed',
        string='Pet Breed',
        related='patient_id.ths_breed_id',
        store=True,
        readonly=True,
        help="Breed of the pet receiving this service."
    )

    boarding_stay_id = fields.Many2one(
        'vet.boarding.stay',
        string='Source Boarding Stay',
        ondelete='cascade',
        index=True,
        copy=False,
    )

    # --- VET-SPECIFIC COMPUTE METHODS ---

    @api.depends('partner_id')
    def _compute_patient_domain(self):
        """
        Compute domain for pets based on selected owner
        """
        for rec in self:
            if rec.partner_id and rec.partner_id.ths_partner_type_id.name == 'Pet Owner':
                # Filter pets by selected owner
                rec.patient_id_domain = str([
                    ('ths_pet_owner_id', '=', rec.partner_id.id),
                    ('ths_partner_type_id.name', '=', 'Pet')
                ])
            else:
                # Show all pets when no owner selected
                rec.patient_id_domain = str([('ths_partner_type_id.name', '=', 'Pet')])

    # --- VET-SPECIFIC ONCHANGE METHODS ---

    @api.onchange('partner_id')
    def _onchange_partner_filter_pets(self):
        """
        When pet owner changes, filter available pets and clear current selection
        """
        if self.partner_id and self.partner_id.ths_partner_type_id.name == 'Pet Owner':
            # Find pets for this owner
            pets = self.env['res.partner'].search([
                ('ths_partner_type_id.name', '=', 'Pet'),
                ('ths_pet_owner_id', '=', self.partner_id.id)
            ])

            # Clear current pet selection if it doesn't belong to new owner
            if self.patient_id and self.patient_id not in pets:
                self.patient_id = False

            # Update domain to show only this owner's pets
            return {
                'domain': {
                    'patient_id': [('id', 'in', pets.ids)] if pets else [('id', '=', False)]
                }
            }
        else:
            # Clear pet selection if no valid owner
            self.patient_id = False
            # Show all pets when no owner selected
            return {
                'domain': {
                    'patient_id': [('ths_partner_type_id.name', '=', 'Pet')]
                }
            }

    @api.onchange('patient_id')
    def _onchange_patient_sync_owner(self):
        """
        When pet is selected, auto-set owner if not already set
        """
        if self.patient_id and self.patient_id.ths_pet_owner_id:
            if not self.partner_id:
                # Auto-set owner if not already set
                self.partner_id = self.patient_id.ths_pet_owner_id
            elif self.partner_id != self.patient_id.ths_pet_owner_id:
                # Show warning if pet doesn't belong to selected owner
                return {
                    'warning': {
                        'title': _('Pet Owner Mismatch'),
                        'message': _(
                            'Pet "%s" belongs to "%s", but billing customer is set to "%s". '
                            'Please select a pet that belongs to the billing customer.',
                            self.patient_id.name,
                            self.patient_id.ths_pet_owner_id.name,
                            self.partner_id.name
                        )
                    }
                }

        # Explicit return for PyCharm
        return None

    @api.onchange('encounter_id')
    def _onchange_encounter_sync_data(self):
        """
        When encounter changes, sync pet owner and available pets
        """
        if self.encounter_id:
            # Check if encounter has vet-specific fields
            if hasattr(self.encounter_id, 'ths_pet_owner_id') and self.encounter_id.ths_pet_owner_id:
                # Set pet owner from encounter
                if not self.partner_id:
                    self.partner_id = self.encounter_id.ths_pet_owner_id

                # Set practitioner from encounter
                if not self.practitioner_id and self.encounter_id.practitioner_id:
                    self.practitioner_id = self.encounter_id.practitioner_id

                # Filter pets to those in the encounter
                if hasattr(self.encounter_id, 'patient_ids') and self.encounter_id.patient_ids:
                    return {
                        'domain': {
                            'patient_id': [('id', 'in', self.encounter_id.patient_ids.ids)]
                        }
                    }

        # Explicit return for PyCharm
        return None

    # --- VET-SPECIFIC CONSTRAINT VALIDATIONS ---

    @api.constrains('partner_id', 'patient_id')
    def _check_vet_billing_consistency(self):
        """
        Validate vet billing consistency:
        1. partner_id must be a Pet Owner
        2. patient_id must be a Pet
        3. Pet must belong to the Pet Owner
        """
        for item in self:
            # Check 1: partner_id must be Pet Owner
            if item.partner_id and item.partner_id.ths_partner_type_id.name != 'Pet Owner':
                raise ValidationError(_(
                    "Billing customer must be a Pet Owner. "
                    "Current: %s (%s)",
                    item.partner_id.name,
                    item.partner_id.ths_partner_type_id.name
                ))

            # Check 2: patient_id must be Pet
            if item.patient_id and item.patient_id.ths_partner_type_id.name != 'Pet':
                raise ValidationError(_(
                    "Patient must be a Pet. "
                    "Current: %s (%s)",
                    item.patient_id.name,
                    item.patient_id.ths_partner_type_id.name
                ))

            # Check 3: Pet must belong to Pet Owner
            if (item.partner_id and item.patient_id and
                    item.patient_id.ths_pet_owner_id != item.partner_id):
                raise ValidationError(_(
                    "Pet '%s' does not belong to Pet Owner '%s'. "
                    "Pet's actual owner: %s",
                    item.patient_id.name,
                    item.partner_id.name,
                    item.patient_id.ths_pet_owner_id.name if item.patient_id.ths_pet_owner_id else 'None'
                ))

    # --- OVERRIDE CREATE/WRITE FOR VET WORKFLOW ---

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to ensure vet-specific validation and defaults
        """
        processed_vals_list = []
        for vals in vals_list:
            # Validate and sync vet-specific relationships
            if vals.get('patient_id') and not vals.get('partner_id'):
                # Auto-set pet owner from pet
                pet = self.env['res.partner'].browse(vals['patient_id'])
                if pet.ths_pet_owner_id:
                    vals['partner_id'] = pet.ths_pet_owner_id.id

            # Validate partner_id is Pet Owner
            if vals.get('partner_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.ths_partner_type_id.name != 'Pet Owner':
                    raise UserError(_(
                        "Billing customer must be a Pet Owner. "
                        "Provided: %s (%s)",
                        partner.name,
                        partner.ths_partner_type_id.name
                    ))

            # Validate patient_id is Pet
            if vals.get('patient_id'):
                patient = self.env['res.partner'].browse(vals['patient_id'])
                if patient.ths_partner_type_id.name != 'Pet':
                    raise UserError(_(
                        "Patient must be a Pet. "
                        "Provided: %s (%s)",
                        patient.name,
                        patient.ths_partner_type_id.name
                    ))

            processed_vals_list.append(vals)

        return super().create(processed_vals_list)

    def write(self, vals):
        """
        Override write to maintain vet-specific relationships
        """
        # Sync pet owner when pet changes
        if 'patient_id' in vals and vals['patient_id'] and 'partner_id' not in vals:
            pet = self.env['res.partner'].browse(vals['patient_id'])
            if pet.ths_pet_owner_id:
                vals['partner_id'] = pet.ths_pet_owner_id.id

        return super().write(vals)

    # --- VET-SPECIFIC BUSINESS METHODS ---

    def _get_billing_summary(self):
        """Get billing summary for vet context"""
        self.ensure_one()
        summary = {
            'pet_owner': self.partner_id.name if self.partner_id else 'No Owner',
            'pet_name': self.patient_id.name if self.patient_id else 'No Pet',
            'pet_species': self.pet_species_id.name if self.pet_species_id else 'Unknown Species',
            'pet_breed': self.pet_breed_id.name if self.pet_breed_id else 'Unknown Breed',
            'service': self.product_id.name if self.product_id else 'No Service',
            'amount': self.qty * self.price_unit * (1 - self.discount / 100),
            'practitioner': self.practitioner_id.name if self.practitioner_id else 'No Practitioner'
        }
        return summary

    def _format_display_name(self):
        """Format display name for vet context"""
        self.ensure_one()
        parts = []

        if self.patient_id:
            parts.append(f"Pet: {self.patient_id.name}")

        if self.product_id:
            parts.append(f"Service: {self.product_id.name}")

        if self.partner_id:
            parts.append(f"Owner: {self.partner_id.name}")

        return " | ".join(parts) if parts else self.name or f"Pending Item #{self.id}"

    def action_view_pet_medical_history(self):
        """View medical history for the pet receiving this service"""
        self.ensure_one()
        if not self.patient_id:
            return {}

        return {
            'name': _('Medical History: %s') % self.patient_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'ths.medical.base.encounter',
            'view_mode': 'list,form',
            'domain': [('patient_ids', 'in', [self.patient_id.id])],
            'context': {
                'search_default_groupby_date': 1,
                'create': False,
            }
        }

    def action_view_owner_billing_history(self):
        """View billing history for the pet owner"""
        self.ensure_one()
        if not self.partner_id:
            return {}

        return {
            'name': _('Billing History: %s') % self.partner_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'ths.pending.pos.item',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {
                'search_default_groupby_state': 1,
                'create': False,
            }
        }

    def action_create_follow_up_service(self):
        """Create follow-up service for the same pet"""
        self.ensure_one()
        if not self.patient_id or not self.partner_id:
            raise UserError(_("Pet and Pet Owner must be set to create follow-up service."))

        return {
            'name': _('Create Follow-up Service'),
            'type': 'ir.actions.act_window',
            'res_model': 'ths.pending.pos.item',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_patient_id': self.patient_id.id,
                'default_practitioner_id': self.practitioner_id.id,
                'default_encounter_id': self.encounter_id.id,
                'default_notes': f"Follow-up for: {self.product_id.name if self.product_id else 'Previous Service'}",
            }
        }

    # --- OVERRIDE POS INTEGRATION FOR VET ---

    def action_reset_to_pending_from_pos(self):
        """
        Override reset action to handle vet-specific validation
        """
        # Validate vet-specific relationships before reset
        for item in self:
            if item.partner_id and item.patient_id:
                if item.patient_id.ths_pet_owner_id != item.partner_id:
                    raise UserError(_(
                        "Cannot reset item: Pet '%s' does not belong to Pet Owner '%s'",
                        item.patient_id.name,
                        item.partner_id.name
                    ))

        return super().action_reset_to_pending_from_pos()

    # TODO: Add integration methods for vet-specific workflows
    def _prepare_pos_order_line_data(self):
        """
        Prepare data for POS order line creation with vet-specific fields
        """
        data = super()._prepare_pos_order_line_data()

        # Add vet-specific data
        data.update({
            'ths_patient_id': self.patient_id.id,  # Individual pet receiving service
            'ths_pet_owner_id': self.partner_id.id,  # Pet owner for billing
            'pet_species': self.pet_species_id.name if self.pet_species_id else '',
            'pet_breed': self.pet_breed_id.name if self.pet_breed_id else '',
        })

        return data

    def _get_vet_service_summary(self):
        """Get summary of veterinary service for reports"""
        self.ensure_one()
        return {
            'service_type': 'Veterinary Service',
            'pet_info': f"{self.patient_id.name} ({self.pet_species_id.name})" if self.patient_id and self.pet_species_id else 'Unknown Pet',
            'owner_info': self.partner_id.name if self.partner_id else 'Unknown Owner',
            'practitioner_info': self.practitioner_id.name if self.practitioner_id else 'Unknown Practitioner',
            'billing_amount': self.qty * self.price_unit * (1 - self.discount / 100),
            'commission_amount': (self.qty * self.price_unit * (1 - self.discount / 100)) * (
                    self.commission_pct / 100) if self.commission_pct else 0,
        }
