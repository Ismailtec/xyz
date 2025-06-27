# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ThsPendingPosItem(models.Model):
    """
    Staging model for billable items generated from backend encounters/appointments,
    waiting to be processed by the Point of Sale.

    For human medical practice:
    - partner_id = Patient (person receiving treatment and responsible for payment)
    - patient_id = Patient (same as partner_id, for consistency)
    """
    _name = 'ths.pending.pos.item'
    _description = 'Pending POS Billing Item'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(compute='_compute_name', store=True, readonly=True)

    encounter_id = fields.Many2one(
        'ths.medical.base.encounter',
        string='Source Encounter',
        ondelete='cascade',
        index=True,
        copy=False,
        help="Daily encounter this item belongs to"
    )
    appointment_id = fields.Many2one(
        'calendar.event',
        string='Source Appointment',
        compute='_compute_appointment_id',
        store=True,
        index=True,
        copy=False
    )

    # For human medical: partner_id = patient (person receiving treatment and paying)
    partner_id = fields.Many2one(
        'res.partner',
        string='Patient',  # In human medical, patient is the customer
        store=True,
        index=True,
        required=True,
        help="The patient receiving treatment and responsible for payment. This is both the service recipient and the billing customer."
    )

    # For human medical: patient_id = partner_id (same person, for consistency)
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient (Recipient)',  # Same as partner_id in human medical
        store=True,
        index=True,
        required=True,
        help="The patient who received the service/product. This is the same person as the billing customer."
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        required=True,
        domain="[('available_in_pos', '=', True), ('sale_ok', '=', True)]"
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
        'appointment.resource',
        string='Practitioner',
        required=True,
        index=True,
        domain="[('ths_resource_category', '=', 'practitioner')]",
        help="The medical staff member who provided this service/item."
    )

    room_id = fields.Many2one(
        'appointment.resource',
        string='Room',
        store=True,
        index=True,
        # readonly=True
    )

    # Commission percentage for this specific line/item/practitioner
    commission_pct = fields.Float(
        string='Commission %',
        digits='Discount',
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
        ondelete='set null',
    )

    notes = fields.Text(string='Internal Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        store=True,
        index=True,
        required=True,
        default=lambda self: self.env.company
    )

    @api.depends('product_id', 'encounter_id', 'patient_id')
    def _compute_name(self):
        for item in self:
            name = item.product_id.name or _("Pending Item")
            if item.patient_id:
                name += f" - {item.patient_id.name}"
            if item.encounter_id:
                name += f" ({item.encounter_id.name})"
            item.name = name

    @api.depends('encounter_id.appointment_ids')
    def _compute_appointment_id(self):
        for record in self:
            record.appointment_id = record.encounter_id.appointment_ids[:1]

    # @api.constrains('partner_id', 'patient_id')
    # def _check_patient_partner_consistency(self):
    #     """
    #     For human medical: ensure partner_id and patient_id are the same person
    #     This constraint enforces the human medical business rule where the patient is the customer
    #     """
    #     for item in self:
    #         if item.partner_id and item.patient_id and item.partner_id != item.patient_id:
    #             raise UserError(_(
    #                 "In human medical practice, the Patient (Recipient) and Patient (Customer) must be the same person. "
    #                 "Patient: %s, Customer: %s",
    #                 item.patient_id.name, item.partner_id.name
    #             ))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """
        For human medical: when partner changes, auto-set patient to same person
        """
        if self.partner_id:
            self.patient_id = self.partner_id

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """
        For human medical: when patient changes, auto-set partner to same person
        """
        if self.patient_id:
            self.partner_id = self.patient_id

    # @api.model_create_multi
    # def create(self, vals_list):
    #     """ Override to link items to daily encounters """
    #     processed_vals_list = []
    #
    #     for vals in vals_list:
    #         # Find or create encounter for this item
    #         if vals.get('partner_id') and not vals.get('encounter_id'):
    #             partner_id = vals['partner_id']
    #             encounter_date = fields.Date.context_today(self)
    #
    #             # Find or create daily encounter
    #             encounter = self.env['ths.medical.base.encounter']._find_or_create_daily_encounter(
    #                 partner_id, encounter_date
    #             )
    #             vals['encounter_id'] = encounter.id
    #
    #         processed_vals_list.append(vals)
    #
    #     return super().create(processed_vals_list)

    # --- Actions ---
    def action_cancel(self):
        """ Manually cancel a pending item. """
        processed_items = self.filtered(lambda i: i.state == 'processed')
        if processed_items:
            _logger.warning("Attempting to cancel already processed pending items: %s. Only setting state.",
                            processed_items.ids)
            # Also unlink from POS line if cancelling a processed item
            processed_items.write({'pos_order_line_id': False})

        self.write({'state': 'cancelled'})
        _logger.info("Cancelled pending items: %s", self.ids)
        return True

    def action_reset_to_pending(self):
        """ Reset a cancelled item back to pending (use with caution). """
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
        items_to_reset = self.filtered(lambda i: i.state in ('processed', 'cancelled'))
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

    def action_view_encounter(self):
        """View the daily encounter for this item"""
        self.ensure_one()
        if not self.encounter_id:
            return {}

        return {
            'name': _('Daily Encounter'),
            'type': 'ir.actions.act_window',
            'res_model': 'ths.medical.base.encounter',
            'view_mode': 'form',
            'res_id': self.encounter_id.id,
            'target': 'current'
        }

# TODO: Add pending item automatic grouping by encounter
# TODO: Implement pending item priority system
# TODO: Add pending item expiration warnings
# TODO: Implement pending item bulk processing
# TODO: Add pending item approval workflow for high-value items