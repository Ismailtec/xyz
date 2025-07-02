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

    # For medical: patient_ids = partner_id (same person, for consistency)
    patient_ids = fields.Many2many(
        'res.partner',
        'ths_pending_pos_patient_rel',
        'encounter_id',
        'patient_id',
        string='Patients',
        domain="[('ths_partner_type_id.is_patient', '=', True)]",
        #related='partner_id',
        readonly=False,
        store=True,
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
    sub_total = fields.Float(
        string='Subtotal',
        compute='_compute_sub_total',
        store=True,
        digits='Product Price',)

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
        domain="[('ths_resource_category', '=', 'location')]",
        # readonly=True
    )
    room_id_domain = fields.Char(
        compute='_compute_room_id_domain',
        store=False,
        help="Domain for selecting the room based on the practitioner."
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

    @api.depends('product_id', 'encounter_id', 'patient_ids')
    def _compute_name(self):
        for item in self:
            name = item.product_id.name or _("Pending Item")
            if item.patient_ids:
                name += f" - {item.patient_ids.name}"
            if item.encounter_id:
                name += f" ({item.encounter_id.name})"
            item.name = name

    @api.depends('encounter_id.appointment_ids')
    def _compute_appointment_id(self):
        for record in self:
            record.appointment_id = record.encounter_id.appointment_ids[:1]

    @api.depends('practitioner_id')
    def _compute_room_id_domain(self):
        """ Compute domain for room_id based on practitioner_id """
        for record in self:
            if record.practitioner_id and record.practitioner_id.ths_department_id:
                record.room_id_domain = str([
                    ('ths_resource_category', '=', 'location'),
                    ('ths_department_id', '=', record.practitioner_id.ths_department_id.id)
                ])
            else:
                record.room_id_domain = str([('ths_resource_category', '=', 'location')])

    @api.depends('qty', 'price_unit', 'discount')
    def _compute_sub_total(self):
        """ Compute the subtotal for this item """
        for item in self:
            if item.discount:
                discount_amount = (item.price_unit * item.qty) * item.discount
                item.sub_total = (item.price_unit * item.qty) - discount_amount
            else:
                item.sub_total = item.price_unit * item.qty

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """  For medical: when partner changes, auto-set patient to same person  """
        if self.partner_id:
            self.patient_ids = self.partner_id

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