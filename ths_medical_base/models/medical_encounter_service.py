# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ThsMedicalEncounterService(models.Model):
    """
    Represents a single billable service or product line within a Medical Encounter.
    For human medical practice: patient = customer (same person receiving care and paying)
    """
    _name = 'ths.medical.encounter.service'
    _description = 'Medical Encounter Service Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    encounter_id = fields.Many2one(
        'ths.medical.base.encounter',
        string='Medical Encounter',
        required=True,
        ondelete='cascade',
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        required=True,
        domain="[('sale_ok', '=', True)]"
    )
    description = fields.Text(
        string='Description',
        compute='_compute_description',
        store=True,
        readonly=False,
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        digits='Product Unit of Measure',
        default=1.0
    )

    # Price and Currency Handling
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
        digits='Product Price'
    )

    # Discount Handling
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0
    )

    # Provider and Commission Handling
    practitioner_id = fields.Many2one(
        'appointment.resource',
        string='Provider',
        index=True,
        #domain="[('ths_is_medical', '=', True)]",
        domain="[('ths_resource_category', '=', 'practitioner')]",
        help="The medical staff member who provided this specific service/item.",
    )
    room_id = fields.Many2one(
        'appointment.resource',
        string='Treatment Room',
        domain="[('ths_resource_category', '=', 'location')]",
        index=True,
        help="The room where this specific service/item was provided.",
    )
    commission_pct = fields.Float(
        string='Commission %',
        digits='Discount',
        help="Commission percentage for the provider for this specific item."
    )

    # Related Fields for Context (mostly invisible in direct line view)
    appointment_id = fields.Many2one(related='encounter_id.appointment_id', store=False)

    # For human medical: partner_id = patient (same person receiving care and paying)
    partner_id = fields.Many2one(
        related='encounter_id.partner_id',
        store=False,
        string="Patient"  # In human medical, patient is the customer
    )
    patient_id = fields.Many2many(
        related='encounter_id.patient_ids',
        store=False,
        string="Patients"  # Same as partner_id in human medical
    )
    notes = fields.Text(string='Line Notes')

    # --- Compute Methods ---
    @api.depends('product_id')
    def _compute_description(self):
        """ Get default description from product. """
        for line in self:
            if not line.product_id:
                line.description = ''
                continue

            # Get product description in partner's language (if partner exists)
            lang_code = line.partner_id.lang if line.partner_id else self.env.user.lang
            product = line.product_id.with_context(lang=lang_code)
            line.description = product.get_product_multiline_description_sale()

    # --- Onchange Methods ---
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """ Update description and price when product changes. """
        if not self.product_id:
            self.price_unit = 0.0
            self.description = ''
            return

        # Set Description
        lang_code = self.partner_id.lang if self.partner_id else self.env.user.lang
        product = self.product_id.with_context(lang=lang_code)
        self.description = product.get_product_multiline_description_sale()

        # Set Price (using default pricelist for simplicity, ideally use encounter/partner pricelist)
        # TODO: Implement proper pricelist logic if needed
        self.price_unit = self.product_id.lst_price

        # Set Default Provider if not already set
        if not self.practitioner_id and self.encounter_id and self.encounter_id.practitioner_id:
            self.practitioner_id = self.encounter_id.practitioner_id

        # TODO: Set default commission based on product/provider configuration

    @api.onchange('quantity', 'discount', 'price_unit')
    def _onchange_price_details(self):
        # Placeholder for potential future logic, e.g., calculating subtotal if needed directly on the line
        pass

    @api.constrains('encounter_id')
    def _check_encounter_consistency(self):
        """
        Validate that the encounter has the necessary data for human medical practice
        """
        for line in self:
            if line.encounter_id:
                encounter = line.encounter_id
                # Ensure encounter has patient data for human medical
                if not encounter.patient_ids:
                    raise UserError(_(
                        "Cannot add service line: Encounter '%s' has no patients assigned.",
                        encounter.name
                    ))
                if not encounter.partner_id:
                    raise UserError(_(
                        "Cannot add service line: Encounter '%s' has no customer/patient assigned.",
                        encounter.name
                    ))

    # --- Additional Methods for Human Medical Context ---
    def _get_billing_partner(self):
        """
        Get the billing partner for this service line.
        For human medical: patient is the billing partner
        """
        self.ensure_one()
        return self.partner_id  # In human medical, patient is the billing customer

    def _get_service_recipient(self):
        """
        Get the service recipient for this service line.
        For human medical: same as billing partner
        """
        self.ensure_one()
        return self.partner_id  # In human medical, same person receives service and pays

    # TODO: Add methods for commission calculation if needed
    # def _calculate_commission_amount(self):
    #     """Calculate commission amount for this service line"""
    #     pass
