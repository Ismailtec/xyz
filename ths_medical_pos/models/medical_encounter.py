# -*- coding: utf-8 -*-

from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class ThsMedicalEncounter(models.Model):
    """ Extend to include medical encounter payments """
    _inherit = 'ths.medical.base.encounter'

    # Service relationships - all services linked to this encounter
    pos_order_ids = fields.One2many(
        'pos.order',
        'encounter_id',
        string='POS Orders',
        help="All POS orders for this encounter"
    )

    # Payment tracking
    total_pending_amount = fields.Float(
        string='Total Pending Amount',
        compute='_compute_payment_status',
        store=True,
        help="Total amount of unpaid items"
    )
    total_paid_amount = fields.Float(
        string='Total Paid Amount',
        compute='_compute_payment_status',
        store=True,
        help="Total amount of paid items"
    )
    has_pending_payments = fields.Boolean(
        string='Has Pending Payments',
        compute='_compute_payment_status',
        store=True,
        help="True if there are unpaid items"
    )

    # --- Compute Methods ---
    @api.depends('pos_order_ids.amount_total', 'pos_order_ids.state')
    def _compute_payment_status(self):
        """Compute payment status from linked POS orders and pending items"""
        for encounter in self:
            # Calculate from POS orders
            paid_orders = encounter.pos_order_ids.filtered(lambda o: o.state == 'paid')
            pending_orders = encounter.pos_order_ids.filtered(lambda o: o.state in ('draft', 'invoiced'))

            encounter.total_paid_amount = sum(paid_orders.mapped('amount_total'))
            encounter.total_pending_amount = sum(pending_orders.mapped('amount_total'))
            encounter.has_pending_payments = encounter.total_pending_amount > 0

            # Update encounter state based on payments
            if encounter.has_pending_payments:
                encounter.state = 'in_progress'
            else:
                encounter.state = 'done'