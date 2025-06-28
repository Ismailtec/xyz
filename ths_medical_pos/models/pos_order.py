# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
# from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Optional: Link back to all pending items processed in this order
    # Useful for traceability, but requires Many2many field and logic to populate.
    ths_processed_pending_item_ids = fields.Many2many(
        'ths.pending.pos.item',
        string='Processed Pending Items (Trace)',
        readonly=True,
        copy=False
    )
    encounter_id = fields.Many2one(
        'ths.medical.base.encounter',
        string='Daily Encounter',
        index=True,
        readonly=True,
        help="Daily encounter this order belongs to"
    )

    # --- Overrides ---

    @api.model
    def _order_fields(self, ui_order):
        """ Include necessary data from the UI order. """
        order_fields = super(PosOrder, self)._order_fields(ui_order)
        # Add custom fields from the order header if any were added
        return order_fields

    # _get_pos_order_lines_values remains challenging for passing arbitrary 'extras' reliably
    # to the backend create method in a standard way across versions.
    # We will focus on processing the data within _process_order after lines are created.

    # def _get_pos_order_lines_values(self, order, session_id):
    #     """ Prepare values for pos.order.line creation, potentially including custom keys """
    #     # Get standard line values
    #     lines_values = super()._get_pos_order_lines_values(order, session_id)
    #
    #     # Add placeholders or extract custom data passed from UI if available
    #     # In Odoo 17+, data might be in ui_order_line.get('server_id') or other keys
    #     # In Odoo 16-, it might be in ui_order_line options or needs post-processing
    #     # For now, we assume the fields will be set *after* line creation in _process_order
    #
    #     # Example structure if data was passed directly (adapt based on actual UI implementation):
    #     # ui_lines = order['lines']
    #     # for idx, ui_line_vals in enumerate(lines_values):
    #     #     ui_line = ui_lines[idx][2] # Odoo 16 structure, may vary
    #     #     ui_line_vals['ths_pending_item_id'] = ui_line.get('ths_pending_item_id')
    #     #     ui_line_vals['ths_patient_ids'] = ui_line.get('ths_patient_ids')
    #     #     ui_line_vals['ths_provider_id'] = ui_line.get('ths_provider_id')
    #     #     ui_line_vals['ths_commission_pct'] = ui_line.get('ths_commission_pct')
    #
    #     return lines_values

    @api.model
    def _process_order(self, order, draft, existing_order=None):
        """
        Override to link pending items but DON'T mark them as processed yet.
        Items are only marked as processed when order is finalized/paid.
        """
        ui_order_lines_data = {line[2]['uuid']: line[2] for line in order.get('lines', []) if
                               len(line) > 2 and 'uuid' in line[2]}
        _logger.debug(f"UI Order Lines Data Keys (UUIDs): {list(ui_order_lines_data.keys())}")

        order_id = super(PosOrder, self)._process_order(order, existing_order)
        _logger.info(f"Processing POS Order ID: {order_id} from UI Order: {order.get('name')}")

        pos_order = self.browse(order_id)
        if not pos_order:
            _logger.error(f"Failed to browse POS Order {order_id} after creation.")
            return order_id

        # Find or create encounter for this order
        if pos_order.partner_id and not pos_order.encounter_id:
            encounter_date = pos_order.date_order.date()
            encounter = self.env['ths.medical.base.encounter']._find_or_create_daily_encounter(
                pos_order.partner_id.id, encounter_date
            )
            pos_order.encounter_id = encounter.id
            _logger.info(f"Linked POS Order {pos_order.name} to encounter {encounter.name}")

        lines_to_update_vals = {}
        pending_items_to_link = {}  # Changed: only link, don't mark as processed yet

        if not ui_order_lines_data and order.get('lines'):
            _logger.warning(
                f"POS Order {pos_order.name}: Could not extract UUID mapping from UI order lines. Cannot process medical data reliably for new order.")
        elif order.get('lines'):
            for line in pos_order.lines:
                line_uuid = line.uuid

                ui_line_data = ui_order_lines_data.get(line_uuid)
                if not ui_line_data:
                    _logger.warning(
                        f"POS Order {pos_order.name}, Line {line.id}: Could not find corresponding UI data using UUID '{line_uuid}'. Skipping medical data processing for this line.")
                    continue

                line_extras = ui_line_data.get('extras', {})
                if not line_extras:
                    _logger.debug(
                        f"POS Order {pos_order.name}, Line {line.id}: No 'extras' found in UI data for UUID '{line_uuid}'.")
                    continue

                _logger.info(
                    f"POS Order {pos_order.name}, Line {line.id} (UUID {line_uuid}): Processing extras: {line_extras}")

                line_update_vals = {}
                pending_item_id = line_extras.get('ths_pending_item_id')
                patient_id = line_extras.get('ths_patient_id')  # For human medical: same as partner
                provider_id = line_extras.get('ths_provider_id')
                commission_pct = line_extras.get('ths_commission_pct')

                if pending_item_id:
                    line_update_vals['ths_pending_item_id'] = pending_item_id
                    # CHANGED: Only link the pending item, don't mark as processed yet
                    pending_items_to_link[pending_item_id] = {'line_id': line.id}

                if patient_id:
                    line_update_vals['ths_patient_id'] = patient_id
                if provider_id:
                    line_update_vals['ths_provider_id'] = provider_id
                if commission_pct is not None:
                    line_update_vals['ths_commission_pct'] = commission_pct

                # Link line to encounter
                if pos_order.encounter_id:
                    line_update_vals['encounter_id'] = pos_order.encounter_id.id

                if line_update_vals:
                    lines_to_update_vals[line.id] = line_update_vals

        # --- Batch Update Lines ---
        if lines_to_update_vals:
            _logger.info(
                f"POS Order {pos_order.name}: Batch updating {len(lines_to_update_vals)} lines with medical data.")
            PosOrderLine = self.env['pos.order.line']
            for line_id, vals in lines_to_update_vals.items():
                try:
                    PosOrderLine.browse(line_id).sudo().write(vals)
                except Exception as e:
                    _logger.error(f"Failed to write medical data to POS Order Line {line_id}: {e}")
                    pos_order.note = (pos_order.note or '') + f"\nError updating line {line_id} medical data: {e}"

        # --- CHANGED: Only link pending items, don't mark as processed yet ---
        if pending_items_to_link:
            pending_item_ids = list(pending_items_to_link.keys())
            _logger.info(
                f"POS Order {pos_order.name}: Linking {len(pending_item_ids)} pending items (not marking as processed yet): {pending_item_ids}")
            PendingItem = self.env['ths.pending.pos.item']
            pending_items = PendingItem.sudo().search([('id', 'in', pending_item_ids)])

            for item in pending_items:
                if item.state == 'pending':
                    try:
                        # CHANGED: Only link the POS line, keep state as 'pending'
                        item.write({
                            'pos_order_line_id': pending_items_to_link[item.id]['line_id'],
                            # DON'T change state to 'processed' yet - wait for order finalization
                        })
                        _logger.info(
                            f"Linked pending item {item.id} to POS line {pending_items_to_link[item.id]['line_id']} (keeping as pending)")
                    except Exception as e:
                        _logger.error(f"Failed to link Pending Item {item.id} to POS Order {pos_order.name}: {e}")
                        pos_order.note = (pos_order.note or '') + f"\nError linking pending item {item.id}: {e}"
                else:
                    _logger.warning(
                        f"Pending Item {item.id} state is '{item.state}', expected 'pending'. Skipping linking.")

        return order_id

    # --- Override action_pos_order_paid to mark pending items as processed ---
    def action_pos_order_paid(self):
        """
        Override to update encounter payment status when order is paid
        """
        res = super(PosOrder, self).action_pos_order_paid()

        for order in self:
            # Update encounter payment status
            if order.encounter_id:
                order.encounter_id._compute_payment_status()
                _logger.info(
                    f"Updated encounter {order.encounter_id.name} payment status after order {order.name} paid")

            # Mark linked pending items as processed
            pending_items = self.env['ths.pending.pos.item'].sudo().search([
                ('pos_order_line_id', 'in', order.lines.ids),
                ('state', '=', 'pending')
            ])

            if pending_items:
                try:
                    pending_items.write({'state': 'processed'})
                    order.write({'ths_processed_pending_item_ids': [(4, item.id) for item in pending_items]})
                    order.message_post(body=_("Processed %d medical pending items.", len(pending_items)))
                    _logger.info(f"Marked {len(pending_items)} pending items as processed for order {order.name}")
                except Exception as e:
                    _logger.error(f"Failed to mark pending items as processed for order {order.name}: {e}")

        return res

    # --- IMPROVED: Refund processing ---
    @api.model
    def _process_refund(self, order, refund_order, original_order):
        """
        Override to handle resetting related medical data on refund.
        This resets pending items back to 'pending' state when refunded.
        """
        _logger.info(f"Processing refund order {refund_order.name} for original order {original_order.name}")

        # Call super first to let Odoo process the standard refund logic
        res = super(PosOrder, self)._process_refund(order, refund_order, original_order)

        items_to_reset = self.env['ths.pending.pos.item']
        encounters_to_check = set()

        # Iterate through the lines of the *new refund order*
        for refund_line in refund_order.lines:
            # Find the original line being refunded
            original_line = refund_line.refunded_orderline_id
            if not original_line:
                _logger.warning(
                    f"Refund line {refund_line.id} in order {refund_order.name} has no link to original line. Skipping medical reset.")
                continue

            # Check if the original line was linked to a pending medical item
            original_pending_item = original_line.ths_pending_item_id
            if original_pending_item:
                _logger.info(
                    f"Original line {original_line.id} (Product: {original_line.product_id.name}) linked to pending item {original_pending_item.id}. Adding item to reset list.")
                items_to_reset |= original_pending_item
                if original_pending_item.encounter_id:
                    encounters_to_check.add(original_pending_item.encounter_id.id)

        # Reset the state of the identified pending items
        if items_to_reset:
            _logger.info(
                f"Attempting to reset state for pending items: {items_to_reset.ids} due to refund order {refund_order.name}")
            try:
                items_to_reset.sudo().action_reset_to_pending_from_pos()
                refund_order.message_post(
                    body=_("Reset %d medical pending items back to 'pending' state.", len(items_to_reset)))
                original_order.message_post(
                    body=_("Reset %d pending items due to refund %s.", len(items_to_reset), refund_order.name))
            except Exception as e:
                _logger.error(f"Failed to reset pending items {items_to_reset.ids}: {e}")
                refund_order.note = (refund_order.note or '') + f"\nError resetting related pending items: {e}"

        # Check if related encounters should be reset from 'billed'
        if encounters_to_check:
            _logger.info(f"Re-checking encounters {list(encounters_to_check)} status after refund.")
            Encounter = self.env['ths.medical.base.encounter']
            encounters = Encounter.sudo().browse(list(encounters_to_check))
            for encounter in encounters:
                # If encounter was billed, check if it now has pending items again
                if encounter.state == 'done':
                    has_pending_now = self.env['ths.pending.pos.item'].sudo().search_count([
                        ('encounter_id', '=', encounter.id),
                        ('state', '=', 'pending')
                    ])
                    if has_pending_now > 0:
                        _logger.info(
                            f"Encounter {encounter.name} now has pending items after refund. Resetting state to 'In Progress'.")
                        try:
                            encounter.write({'state': 'in_progress'})
                            encounter.message_post(
                                body=_("Encounter status reset to 'In Progress' due to POS Order refund."))
                        except Exception as e:
                            _logger.error(f"Failed to reset encounter {encounter.name} state after refund: {e}")
                            refund_order.note = (
                                                        refund_order.note or '') + f"\nError resetting encounter {encounter.name} state: {e}"

        return res

    # --- NEW: Helper method to check order payment status ---
    def _is_order_finalized(self):
        """
        Check if the order is finalized (paid, invoiced, or done).
        Used to determine when to mark pending items as processed.
        """
        self.ensure_one()
        return self.state in ('paid', 'done', 'invoiced')

    # --- Method to manually sync pending items (for data recovery) ---
    def action_sync_pending_items_state(self):
        """
        Manual action to sync pending items state based on order status.
        Useful for data recovery or fixing inconsistent states.
        """
        for order in self:
            pending_items = self.env['ths.pending.pos.item'].sudo().search([
                ('pos_order_line_id', 'in', order.lines.ids)
            ])

            if order._is_order_finalized():
                # Order is finalized, pending items should be 'processed'
                items_to_process = pending_items.filtered(lambda i: i.state == 'pending')
                if items_to_process:
                    items_to_process.write({'state': 'processed'})
                    _logger.info(
                        f"Manually marked {len(items_to_process)} items as processed for finalized order {order.name}")
            else:
                # Order is not finalized, pending items should be 'pending'
                items_to_reset = pending_items.filtered(lambda i: i.state == 'processed')
                if items_to_reset:
                    items_to_reset.write({'state': 'pending'})
                    _logger.info(
                        f"Manually reset {len(items_to_reset)} items to pending for non-finalized order {order.name}")

        return True

    def action_view_encounter(self):
        """View the daily encounter for this order"""
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

    # TODO: Add encounter-based POS order grouping
    # TODO: Implement encounter payment plan integration
    # TODO: Add encounter insurance claim generation
    # TODO: Implement encounter loyalty point calculations
    # TODO: Add encounter receipt customization
    # TODO: Implement encounter automatic receipt email