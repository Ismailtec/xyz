# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ThsMedicalEncounterService(models.Model):
    """ Represents a single billable service or product line within a Medical Encounter. """
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
        domain="[('sale_ok', '=', True)]"  # Ensure it's sellable
    )
    description = fields.Text(
        string='Description',
        compute='_compute_description',
        store=True,
        readonly=False,  # Allow manual override
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
    # currency_id = fields.Many2one(
    #     related='company.currency_id',
    #     string='Currency',
    #     readonly=True
    # )
    # Discount Handling
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0
    )
    # Provider and Commission Handling
    practitioner_id = fields.Many2one(
        'hr.employee',
        string='Provider',
        index=True,
        domain="[('ths_is_medical', '=', True)]",
        help="The medical staff member who provided this specific service/item.",
        # Default practitioner from encounter can be set via context in the view
    )
    commission_pct = fields.Float(
        string='Commission %',
        digits='Discount',  # Use discount precision for percentage
        help="Commission percentage for the provider for this specific item."
    )
    # Related Fields for Context (mostly invisible in direct line view)
    appointment_id = fields.Many2one(related='encounter_id.appointment_id', store=False)
    partner_id = fields.Many2one(related='encounter_id.partner_id', store=False, string="Customer/Owner")
    patient_id = fields.Many2one(related='encounter_id.patient_id', store=False, string="Patient")
    #company_id = fields.Many2one(related='encounter_id.company_id', store=True, index=True)
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

        # Reset quantity if UoM changes implicitly? For now, keep quantity.
        # self.quantity = 1.0

        # Set Description
        lang_code = self.partner_id.lang if self.partner_id else self.env.user.lang
        product = self.product_id.with_context(lang=lang_code)
        self.description = product.get_product_multiline_description_sale()

        # Set Price (using default pricelist for simplicity, ideally use encounter/partner pricelist)
        # TODO: Implement proper pricelist logic if needed
        self.price_unit = self.product_id.lst_price

        # Set Default Provider? If not already set.
        if not self.practitioner_id and self.encounter_id and self.encounter_id.practitioner_id:
            self.practitioner_id = self.encounter_id.practitioner_id

        # TODO: Set default commission based on product/provider?

    @api.onchange('quantity', 'discount', 'price_unit')
    def _onchange_price_details(self):
        # Placeholder for potential future logic, e.g., calculating subtotal if needed directly on the line
        pass
