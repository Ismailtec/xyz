# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging  # Import logging

_logger = logging.getLogger(__name__)  # Define logger


class ThsPendingPosItem(models.Model):
    """
    Staging model for billable items generated from backend encounters/appointments,
    waiting to be processed by the Point of Sale.
    """
    _name = 'ths.pending.pos.item'
    _description = 'Pending POS Billing Item'
    _order = 'create_date desc'  # Show newest first
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Add chatter

    name = fields.Char(compute='_compute_name', store=True, readonly=True)  # Added Name field
    encounter_id = fields.Many2one(
        'ths.medical.base.encounter',
        string='Source Encounter',
        ondelete='cascade',  # If encounter deleted, remove pending items
        index=True,
        copy=False
    )
    appointment_id = fields.Many2one(
        'calendar.event',
        string='Source Appointment',
        related='encounter_id.appointment_id',  # Get from encounter
        store=True,  # Store for easier searching/reporting
        index=True,
        copy=False
    )
    # Owner/Customer responsible for payment
    partner_id = fields.Many2one(
        'res.partner', string='Customer/Owner',
        # related='encounter_id.partner_id', # Make editable or set on create
        store=True, index=True, required=True,
        help="The customer responsible for payment (usually the pet owner or main patient contact)."
    )
    # Patient receiving the service (human or animal)
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        # related='encounter_id.patient_id', # Make editable or set on create
        store=True, index=True, required=True,
        help="The patient who received the service/product."
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        required=True,
        domain="[('available_in_pos', '=', True), ('sale_ok', '=', True)]"  # Should be sellable in POS
    )
    description = fields.Text(
        string='Description',
        help="Optional override for the product description on the POS line."
    )
    qty = fields.Float(
        string='Quantity',
        required=True,
        digits='Product Unit of Measure',
        default=1.0
    )
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
        digits='Product Price'
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0
    )
    # Practitioner who provided the service (for commission/reporting)
    practitioner_id = fields.Many2one(
        'hr.employee',
        string='Practitioner',
        required=True,
        index=True,
        domain="[('ths_is_medical', '=', True)]",
        help="The medical staff member who provided this service/item."
    )
    # Commission percentage for this specific line/item/practitioner
    commission_pct = fields.Float(
        string='Commission %',
        digits='Discount',  # Use discount precision for percentage
        help="Commission percentage for the practitioner for this specific item."
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('processed', 'Processed in POS'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='pending', required=True, index=True, copy=False, tracking=True)

    # Link to the POS order line created from this item
    pos_order_line_id = fields.Many2one(
        'pos.order.line',
        string='POS Order Line',
        readonly=True,
        copy=False,
        # When POS line is deleted (e.g. order deleted), unlink pending item? Or just clear link?
        ondelete='set null',  # Clear link if POS line deleted
    )

    notes = fields.Text(string='Internal Notes')
    company_id = fields.Many2one(
        'res.company', string='Company',
        # related='encounter_id.company_id', # Set on create?
        store=True, index=True, required=True, default=lambda self: self.env.company)

    @api.depends('product_id', 'encounter_id', 'patient_id')
    def _compute_name(self):
        for item in self:
            name = item.product_id.name or _("Pending Item")
            if item.patient_id:
                name += f" - {item.patient_id.name}"
            if item.encounter_id:
                name += f" ({item.encounter_id.name})"
            item.name = name

    # --- Actions ---
    def action_cancel(self):
        """ Manually cancel a pending item. """
        # Prevent cancelling already processed items? Or allow cancellation which triggers reversal logic?
        # For now, only cancel pending/processed. If processed, need to handle consequences.
        processed_items = self.filtered(lambda i: i.state == 'processed')
        if processed_items:
            # TODO: Add logic here later if needed to handle cancellation of *processed* items,
            # e.g., check corresponding POS order, notify user, maybe block cancellation.
            _logger.warning("Attempting to cancel already processed pending items: %s. Only setting state.",
                            processed_items.ids)
            # raise UserError(_("Cannot directly cancel items already processed in POS. Consider returning the POS order."))

        # Also unlink from POS line if cancelling a processed item
        processed_items.write({'pos_order_line_id': False})
        self.write({'state': 'cancelled'})
        _logger.info("Cancelled pending items: %s", self.ids)
        return True

    def action_reset_to_pending(self):
        """ Reset a cancelled item back to pending (use with caution). """
        # Prevent resetting items that were processed (should use refund flow)
        if any(item.state == 'processed' for item in self):
            raise UserError(_("Cannot reset items that have already been processed in Point of Sale via this action."))
        # Only allow reset from 'cancelled' state
        items_to_reset = self.filtered(lambda i: i.state == 'cancelled')
        if items_to_reset:
            items_to_reset.write({'state': 'pending'})
            _logger.info("Reset cancelled pending items to pending: %s", items_to_reset.ids)
        return True

    def action_reset_to_pending_from_pos(self):
        """
        Action specifically called when a linked POS line is refunded.
        Resets state to 'pending' and unlinks the POS line.
        """
        _logger.info("Action 'Reset to Pending from POS' called for items: %s", self.ids)
        items_to_reset = self.filtered(
            lambda i: i.state in ('processed', 'cancelled'))  # Allow reset even if previously cancelled manually
        if not items_to_reset:
            _logger.warning("No items found in 'processed' or 'cancelled' state to reset from POS refund for ids: %s",
                            self.ids)
            return False

        # Unlink from POS line and set back to pending
        vals_to_write = {
            'state': 'pending',
            'pos_order_line_id': False
        }
        items_to_reset.write(vals_to_write)
        _logger.info("Reset pending items %s state to 'pending' and unlinked POS line due to refund.",
                     items_to_reset.ids)

        # Post message on items
        for item in items_to_reset:
            item.message_post(body=_("Item status reset to 'Pending' due to linked POS Order Line refund."))

        return True
