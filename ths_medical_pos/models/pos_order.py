# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Optional: Link back to all pending items processed in this order
    # Useful for traceability, but requires Many2many field and logic to populate.
    # ths_processed_pending_item_ids = fields.Many2many(
    #     'ths.pending.pos.item',
    #     string='Processed Pending Items (Trace)',
    #     readonly=True,
    #     copy=False
    # )

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
    #     #     ui_line_vals['ths_patient_id'] = ui_line.get('ths_patient_id')
    #     #     ui_line_vals['ths_provider_id'] = ui_line.get('ths_provider_id')
    #     #     ui_line_vals['ths_commission_pct'] = ui_line.get('ths_commission_pct')
    #
    #     return lines_values

    @api.model
    def _process_order(self, order, draft, existing_order):
        """ Override to link pending items and update encounter state. """
        # --- (Keep the existing refined _process_order logic from previous step) ---
        ui_order_lines_data = {line[2]['uid']: line[2] for line in order.get('lines', []) if
                               len(line) > 2 and 'uid' in line[2]}
        _logger.debug(f"UI Order Lines Data Keys (UIDs): {list(ui_order_lines_data.keys())}")

        order_id = super(PosOrder, self)._process_order(order, draft, existing_order)
        _logger.info(f"Processing POS Order ID: {order_id} from UI Order: {order.get('name')}")

        pos_order = self.browse(order_id)
        if not pos_order:
            _logger.error(f"Failed to browse POS Order {order_id} after creation.")
            return order_id

        pending_items_to_update = {}
        lines_to_update_vals = {}
        encounter_ids_to_check = set()

        if not ui_order_lines_data and order.get('lines'):
            _logger.warning(
                f"POS Order {pos_order.name}: Could not extract UID mapping from UI order lines. Cannot process medical data reliably for new order.")
            # If it's an existing order being modified maybe UID isn't relevant? Need careful check.
        elif order.get('lines'):
            for line in pos_order.lines:
                line_uid = line.pos_order_line_uid  # Odoo 17+ field? Check this field exists.

                ui_line_data = ui_order_lines_data.get(line_uid)

                if not ui_line_data:
                    _logger.warning(
                        f"POS Order {pos_order.name}, Line {line.id}: Could not find corresponding UI data using UID '{line_uid}'. Skipping medical data processing for this line.")
                    continue

                line_extras = ui_line_data.get('extras', {})
                if not line_extras:
                    _logger.debug(
                        f"POS Order {pos_order.name}, Line {line.id}: No 'extras' found in UI data for UID '{line_uid}'.")
                    continue

                _logger.info(
                    f"POS Order {pos_order.name}, Line {line.id} (UID {line_uid}): Processing extras: {line_extras}")

                line_update_vals = {}
                pending_item_id = line_extras.get('ths_pending_item_id')
                patient_id = line_extras.get('ths_patient_id')
                provider_id = line_extras.get('ths_provider_id')
                commission_pct = line_extras.get('ths_commission_pct')

                if pending_item_id:
                    line_update_vals['ths_pending_item_id'] = pending_item_id
                    pending_items_to_update[pending_item_id] = {'line_id': line.id}

                if patient_id: line_update_vals['ths_patient_id'] = patient_id
                if provider_id: line_update_vals['ths_provider_id'] = provider_id
                if commission_pct is not None: line_update_vals['ths_commission_pct'] = commission_pct

                if line_update_vals: lines_to_update_vals[line.id] = line_update_vals

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

        # --- Batch Update Pending Items ---
        if pending_items_to_update:
            pending_item_ids = list(pending_items_to_update.keys())
            _logger.info(
                f"POS Order {pos_order.name}: Processing {len(pending_item_ids)} linked pending items: {pending_item_ids}")
            PendingItem = self.env['ths.pending.pos.item']
            pending_items = PendingItem.sudo().search([('id', 'in', pending_item_ids)])

            for item in pending_items:
                if item.state == 'pending':
                    try:
                        item.write({
                            'pos_order_line_id': pending_items_to_update[item.id]['line_id'],
                            'state': 'processed'
                        })
                        if item.encounter_id:
                            encounter_ids_to_check.add(item.encounter_id.id)
                    except Exception as e:
                        _logger.error(f"Failed to update Pending Item {item.id} from POS Order {pos_order.name}: {e}")
                        pos_order.note = (pos_order.note or '') + f"\nError updating pending item {item.id}: {e}"
                elif item.state == 'processed' and item.pos_order_line_id.id == pending_items_to_update[item.id][
                    'line_id']:
                    _logger.warning(
                        f"Pending Item {item.id} already processed and linked to correct line {item.pos_order_line_id.id}. Skipping update.")
                    if item.encounter_id: encounter_ids_to_check.add(
                        item.encounter_id.id)  # Still check encounter state
                else:
                    _logger.warning(
                        f"Pending Item {item.id} was expected to be linked but state is '{item.state}' or linked line mismatch. Skipping update.")

        # --- Batch Update Encounters ---
        if encounter_ids_to_check:
            _logger.info(
                f"POS Order {pos_order.name}: Checking encounters {list(encounter_ids_to_check)} for update to 'billed' state.")
            Encounter = self.env['ths.medical.base.encounter']
            PendingItem = self.env['ths.pending.pos.item']
            encounters = Encounter.sudo().browse(list(encounter_ids_to_check))
            for encounter in encounters:
                # Check if *any* pending item for this encounter is still in 'pending' state
                remaining_pending = PendingItem.sudo().search_count([
                    ('encounter_id', '=', encounter.id),
                    ('state', '=', 'pending')
                ])
                if remaining_pending == 0:
                    if encounter.state != 'billed':
                        _logger.info(f"Updating Encounter {encounter.name} state to 'billed'.")
                        try:
                            encounter.write({'state': 'billed'})  # Already sudo'd
                        except Exception as e:
                            _logger.error(f"Failed to update Encounter {encounter.name} state: {e}")
                            pos_order.note = (
                                                     pos_order.note or '') + f"\nError updating encounter {encounter.name}: {e}"
                # else: # No need to log if still pending

        return order_id

    # --- ADD REFUND PROCESSING ---
    @api.model
    def _process_refund(self, order, refund_order, original_order):
        """
        Override to handle resetting related medical data on refund.
        This method is called by the standard refund action.
        `order`: The original UI order data for the refund.
        `refund_order`: The newly created backend pos.order record for the refund.
        `original_order`: The original backend pos.order record being refunded.
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
            # else: # Optional log
            #    _logger.debug(f"Original line {original_line.id} was not linked to a pending medical item.")

        # Reset the state of the identified pending items
        if items_to_reset:
            _logger.info(
                f"Attempting to reset state for pending items: {items_to_reset.ids} due to refund order {refund_order.name}")
            try:
                items_to_reset.sudo().action_reset_to_pending_from_pos()
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
                if encounter.state == 'billed':
                    has_pending_now = self.env['ths.pending.pos.item'].sudo().search_count([
                        ('encounter_id', '=', encounter.id),
                        ('state', '=', 'pending')
                    ])
                    if has_pending_now > 0:
                        _logger.info(
                            f"Encounter {encounter.name} now has pending items after refund. Resetting state to 'Ready For Billing'.")
                        try:
                            encounter.write({'state': 'ready_for_billing'})
                            encounter.message_post(
                                body=_("Encounter status reset to 'Ready For Billing' due to POS Order refund."))
                        except Exception as e:
                            _logger.error(f"Failed to reset encounter {encounter.name} state after refund: {e}")
                            refund_order.note = (
                                                        refund_order.note or '') + f"\nError resetting encounter {encounter.name} state: {e}"

        # --- Trigger Commission Reversal ---
        # This part needs to be handled by the ths_medical_commission module
        # Ideally, ths_medical_commission overrides _process_refund, calls super(),
        # then finds and cancels its own commission lines linked to the refunded order lines.
        _logger.info(f"TODO: Trigger commission cancellation logic for refunded lines in order {refund_order.name}.")
        # Example placeholder call (actual implementation in ths_medical_commission):
        # self.env['ths.medical.commission.line'].sudo().cancel_for_refunded_pos_lines(refund_order.lines.mapped('refunded_orderline_id'))

        return res
