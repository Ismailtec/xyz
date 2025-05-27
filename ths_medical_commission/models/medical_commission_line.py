# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ThsMedicalCommissionLine(models.Model):
    _name = 'ths.medical.commission.line'
    _description = 'Medical Commission Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Add chatter
    _order = 'date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    pos_order_line_id = fields.Many2one(
        'pos.order.line',
        string='POS Order Line',
        required=True,
        ondelete='cascade',  # If POS line deleted, remove commission line
        index=True,
        copy=False,
        readonly=True,
    )
    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
        related='pos_order_line_id.order_id',
        store=True,
        index=True,
        readonly=True,
    )
    pos_session_id = fields.Many2one(
        'pos.session',
        string='POS Session',
        related='pos_order_id.session_id',
        store=True,
        index=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        related='pos_order_line_id.product_id',
        store=True,
        readonly=True,
    )
    provider_id = fields.Many2one(
        'hr.employee',
        string='Provider',
        related='pos_order_line_id.ths_provider_id',  # Get from the custom field
        store=True,  # Store for easier grouping/reporting
        index=True,
        readonly=True,
    )
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',  # Changed label to generic Patient
        related='pos_order_line_id.ths_patient_id',  # Get from the custom field
        store=True,  # Store for easier grouping/reporting
        index=True,
        readonly=True,
    )
    commission_rate = fields.Float(
        string='Rate (%)',
        related='pos_order_line_id.ths_commission_pct',  # Get from the custom field
        store=True,
        digits='Discount',
        readonly=True,
    )
    # Base amount for commission calculation (e.g., price_subtotal or price_subtotal_incl)
    base_amount = fields.Monetary(
        string='Base Amount',
        compute='_compute_base_and_commission',
        store=True,
        currency_field='currency_id',
        help="Amount on which the commission rate is applied (typically Price Subtotal)."
    )
    commission_amount = fields.Monetary(
        string='Commission Amount',
        compute='_compute_base_and_commission',
        store=True,
        currency_field='currency_id',
        help="Calculated commission (Base Amount * Rate / 100)."
    )
    date = fields.Datetime(
        string='Date',
        related='pos_order_id.date_order',
        store=True,
        index=True,
        readonly=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),  # Ready to be included in payout
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')  # e.g., if POS order is returned/refunded
    ], string='Status', default='draft', index=True, copy=False, tracking=True, readonly=True)  # Added tracking=True
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='pos_order_id.company_id',
        store=True, index=True, readonly=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='pos_order_id.currency_id',
        store=True,  # Store for monetary fields
        readonly=True,
    )
    notes = fields.Text(string='Notes')

    # TODO: Add fields related to payout (e.g., payout_batch_id, payment_id) later

    @api.depends('provider_id', 'pos_order_line_id')
    def _compute_name(self):
        for line in self:
            name = _("Commission")
            if line.provider_id:
                name += f" - {line.provider_id.name}"
            if line.pos_order_line_id:
                name += f" ({line.pos_order_line_id.order_id.name or 'Draft Order'} / {line.pos_order_line_id.product_id.name or 'N/A'})"
            line.name = name

    @api.depends('pos_order_line_id.price_subtotal_incl', 'pos_order_line_id.price_subtotal', 'commission_rate')
    def _compute_base_and_commission(self):
        """ Calculate base amount and commission amount """
        for line in self:
            # Defaulting to price_subtotal (excl tax).
            base = line.pos_order_line_id.price_subtotal if line.pos_order_line_id else 0.0
            rate = line.commission_rate or 0.0
            line.base_amount = base
            line.commission_amount = (base * rate) / 100.0

    # --- Actions ---
    def action_cancel(self):
        """Set the commission line state to cancelled."""
        cancelled_count = 0
        for line in self:
            if line.state not in ('paid', 'cancelled'):  # Prevent cancelling already paid or cancelled lines
                line.write({'state': 'cancelled'})
                line.message_post(body=_("Commission line cancelled."))
                cancelled_count += 1
                _logger.info(f"Cancelled commission line {line.id} linked to POS line {line.pos_order_line_id.id}")
            elif line.state == 'paid':
                _logger.warning(f"Attempted to cancel already paid commission line {line.id}.")
                line.message_post(body=_("Warning: Cannot cancel commission line as it is already marked as paid."))
            # else: Do nothing if already cancelled

        if cancelled_count > 0:
            # Optionally return a notification for interactive use
            # return { ... notification action ... }
            pass
        return True

    # def action_confirm(self):
    #     self.write({'state': 'confirmed'})
    #
    # def action_mark_paid(self):
    #     self.write({'state': 'paid'})
    #
    # def action_reset_to_draft(self):
    #     # Use caution with resets, ensure it's allowed
    #     items_to_reset = self.filtered(lambda l: l.state == 'cancelled')
    #     items_to_reset.write({'state': 'draft'})
