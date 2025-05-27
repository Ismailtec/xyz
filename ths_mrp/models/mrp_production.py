# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError  # Import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # --- Fields ---
    ths_effective_date = fields.Date(
        string="Effective Date",
        compute='_compute_ths_effective_date',
        store=True,
        copy=False,
        index=True,
        help="Effective date used for stock moves and accounting entries. Automatically set from Planned Date.",
        readonly=True,  # Keep readonly as it's computed
        tracking=True
    )

    # --- Compute Method ---
    @api.depends('date_start')
    def _compute_ths_effective_date(self):
        """ Sets the effective date based on the planned start date (date_start) """
        for production in self:
            if production.date_start:
                production.ths_effective_date = production.date_start.date()
            else:
                production.ths_effective_date = fields.Date.context_today(production)

    # --- Overridden Methods ---
    def button_mark_done(self):
        """
        Override button_mark_done:
        1. Ensure ths_effective_date is computed.
        2. Pass date to context and write to moves BEFORE super().
        3. Write effective date to date_finished AFTER super().
        """
        self.ensure_one()
        self._compute_ths_effective_date()  # Ensure computed

        final_date_to_use = self.ths_effective_date
        _logger.info(f"MRP {self.name}: Validating with Effective Date: {final_date_to_use}")

        context_with_date = self.env.context.copy()
        if final_date_to_use:
            context_with_date['force_period_date'] = final_date_to_use
            _logger.info(f"MRP {self.name}: Adding force_period_date={final_date_to_use} to context.")

            moves_to_update = self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            moves_to_update |= self.move_finished_ids.filtered(lambda m: m.state not in ('done', 'cancel'))

            if moves_to_update:
                _logger.info(
                    f"MRP {self.name}: Applying ths_effective_date {final_date_to_use} to {len(moves_to_update)} moves.")
                try:
                    moves_to_update.sudo().write({'ths_effective_date': final_date_to_use})
                except Exception as e:
                    _logger.error(f"MRP {self.name}: Failed to write ths_effective_date to moves: {e}")

        # Call super with the potentially modified context
        res = super(MrpProduction, self.with_context(context_with_date)).button_mark_done()

        # --- Set date_finished AFTER super() ---
        if final_date_to_use and self.state == 'done':  # Check state after super
            # Combine Date with current time (or start/end of day?)
            # Using start of day for consistency
            effective_datetime = datetime.combine(final_date_to_use, datetime.min.time())
            _logger.info(f"MRP {self.name}: Setting date_finished to {effective_datetime}")
            try:
                # Need sudo? Usually system can write after validation. Try without first.
                self.write({'date_finished': effective_datetime})
            except Exception as e:
                _logger.error(f"MRP {self.name}: Failed to write date_finished: {e}")
        # --- End Set date_finished ---

        return res

    # --- Placeholder for Unbuild Action Override ---
    # Need to identify the correct method that creates unbuild orders from MOs
    # Example name, might be different:
    # def action_generate_unbuild_order(self):
    #    res = super().action_generate_unbuild_order()
    #    # Add logic here to find the created unbuild order(s) from res
    #    # and write self.ths_effective_date to their ths_effective_date field
    #    # Example:
    #    # if isinstance(res, dict) and res.get('res_id'):
    #    #    unbuild_order = self.env['stock.unbuild'].browse(res['res_id'])
    #    #    if self.ths_effective_date:
    #    #        unbuild_order.write({'ths_effective_date': self.ths_effective_date})
    #    return res
