# -*- coding: utf-8 -*-

from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    # Link back to the source pending item
    ths_pending_item_id = fields.Many2one(
        'ths.pending.pos.item',
        string='Source Pending Item',
        readonly=True,
        copy=False  # Don't copy this link if the order/line is duplicated
    )
    # Store Patient (even if different from order's main partner)
    ths_patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        readonly=True,
        copy=False,
        help="Patient who received this specific service/product."
    )
    # Store Provider for commission/reporting
    ths_provider_id = fields.Many2one(
        'hr.employee',
        string='Provider',
        readonly=True,
        copy=False,
        help="Medical staff member who provided this service/item."
    )
    # Store specific commission rate for this line
    ths_commission_pct = fields.Float(
        string='Commission %',
        digits='Discount',  # Re-use discount precision
        readonly=True,
        copy=False,
        help="Specific commission percentage for the provider on this line."
    )

    def export_for_ui(self):
        """ Add custom fields to the data sent to the POS UI """
        # In Odoo 16+, export_for_ui structure changed slightly.
        # We need to get the result from super() first.
        line_data = super().export_for_ui()
        # Add our custom fields
        line_data['ths_pending_item_id'] = self.ths_pending_item_id.id
        line_data['ths_patient_id'] = self.ths_patient_id.id
        line_data['ths_provider_id'] = self.ths_provider_id.id
        line_data['ths_commission_pct'] = self.ths_commission_pct
        return line_data

    # Note: The process of getting data *back* from the UI (create_from_ui)
    # often involves passing data via the 'options' dictionary or processing
    # after the line is created based on other context. We'll handle setting
    # these fields based on the pending item when the line is added via the POS widget.
