# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    # IMPORTANT: This inherits pos.order. If ths_medical_pos also inherits pos.order,
    # ensure the dependency order is correct so this module inherits the changes from ths_medical_pos.
    # Odoo's inheritance mechanism handles calling the 'parent' override via super().
    _inherit = 'pos.order'

    commission_line_ids = fields.One2many(
        'ths.medical.commission.line',
        'pos_order_id',
        string="Commission Lines",
        readonly=True,
        copy=False
    )

    def _create_commission_lines(self):
        """ Create commission lines for the order """
        # (Keep the existing logic from the previous step)
        self.ensure_one()
        CommissionLine = self.env['ths.medical.commission.line']
        commission_vals_list = []
        created_lines = self.env['ths.medical.commission.line']

        _logger.info(f"POS Order {self.name}: Checking lines for commission generation.")

        for line in self.lines:
            if line.ths_provider_id and line.ths_commission_pct > 0:
                _logger.debug(f"  - Line {line.id} (Product: {line.product_id.name}): Provider {line.ths_provider_id.name}, Rate {line.ths_commission_pct}%. Creating commission line.")
                vals = {
                    'pos_order_line_id': line.id,
                    'state': 'draft',
                }
                commission_vals_list.append(vals)

        if commission_vals_list:
            try:
                created_lines = CommissionLine.sudo().create(commission_vals_list)
                _logger.info(f"POS Order {self.name}: Created {len(created_lines)} commission lines.")
                self.message_post(body=_("Generated %d commission line(s).", len(created_lines)))
            except Exception as e:
                _logger.error(f"POS Order {self.name}: Failed to create commission lines: {e}")
                self.message_post(body=_("Error generating commission lines: %s", e))

        return created_lines

    def action_pos_order_paid(self):
        """ Override to generate commission lines after payment validation """
        # (Keep the existing logic from the previous step)
        res = super(PosOrder, self).action_pos_order_paid()
        for order in self:
            if not order.commission_line_ids and order.state in ('paid', 'done', 'invoiced'):
                order._create_commission_lines()
            elif order.commission_line_ids:
                 _logger.warning(f"POS Order {order.name}: Commission lines already exist. Skipping generation in action_pos_order_paid.")

        return res


    # --- REFUND PROCESSING OVERRIDE ---
    @api.model
    def _process_refund(self, order, refund_order, original_order):
        """
        Override to cancel related commission lines after standard refund processing.
        """
        _logger.info(f"Commission Module: Processing refund {refund_order.name} for original order {original_order.name}")
        # === 1. Call Super ===
        # This executes the logic in ths_medical_pos (resetting pending items/encounters)
        # and the standard Odoo refund logic.
        res = super(PosOrder, self)._process_refund(order, refund_order, original_order)

        # === 2. Cancel Related Commission Lines ===
        # Get the IDs of the original lines that were refunded
        original_line_ids = refund_order.lines.mapped('refunded_orderline_id').ids
        if not original_line_ids:
            _logger.info(f"Commission Module: No original lines found for refund {refund_order.name}. No commissions to cancel.")
            return res

        _logger.info(f"Commission Module: Searching for commission lines linked to original POS lines {original_line_ids} for refund {refund_order.name}.")
        CommissionLine = self.env['ths.medical.commission.line']
        # Find commission lines linked to the original refunded lines that are not already cancelled
        commission_lines_to_cancel = CommissionLine.sudo().search([
            ('pos_order_line_id', 'in', original_line_ids),
            ('state', '!=', 'cancelled')
        ])

        if commission_lines_to_cancel:
            _logger.info(f"Commission Module: Found {len(commission_lines_to_cancel)} commission lines to cancel for refund {refund_order.name}: {commission_lines_to_cancel.ids}")
            try:
                commission_lines_to_cancel.action_cancel() # Call the cancel action on the lines
                refund_order.message_post(body=_("Cancelled %d related commission line(s).", len(commission_lines_to_cancel)))
                original_order.message_post(body=_("Cancelled %d commission line(s) due to refund %s.", len(commission_lines_to_cancel), refund_order.name))
            except Exception as e:
                 _logger.error(f"Commission Module: Failed to cancel commission lines {commission_lines_to_cancel.ids} for refund {refund_order.name}: {e}")
                 refund_order.message_post(body=_("Error cancelling related commission lines: %s", e))
        else:
             _logger.info(f"Commission Module: No active commission lines found for refunded lines in order {refund_order.name}.")

        return res