# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class StockUnbuild(models.Model):
    _inherit = 'mrp.unbuild'

    # --- Effective Date Field (Computed from MO) ---
    @api.depends('mo_id', 'mo_id.ths_effective_date')
    def _compute_ths_effective_date(self):
        """ Compute the effective date from the linked Manufacturing Order. """
        for unbuild in self:
            if unbuild.mo_id and unbuild.mo_id.ths_effective_date:
                unbuild.ths_effective_date = unbuild.mo_id.ths_effective_date
            else:
                # Fallback if no MO linked or MO has no effective date
                unbuild.ths_effective_date = fields.Date.context_today(unbuild)

    ths_effective_date = fields.Date(
        string="Effective Date",
        compute='_compute_ths_effective_date',
        store=True,
        copy=False,
        index=True,
        help="Effective date for the stock moves and accounting entries related to this unbuild order. Derived from the Manufacturing Order.",
        readonly=False
    )

    # --- Override Unbuild Action ---
    def action_unbuild(self):
        """
        Override to pass effective date in context.
        Moves will get date via _generate_moves override.
        """
        # Process records one by one to handle context/dates correctly
        res = False
        for unbuild in self:
            # Ensure compute method has run (might be needed if called programmatically)
            unbuild._compute_ths_effective_date()
            final_date_to_use = unbuild.ths_effective_date  # Use the computed/stored value
            _logger.info(f"Unbuild {unbuild.name}: Starting action_unbuild with Effective Date: {final_date_to_use}")

            # Prepare context BEFORE calling super
            context_with_date = {**self.env.context, 'force_period_date': final_date_to_use}

            # Call super with context (it will call _generate_moves)
            current_res = super(StockUnbuild, unbuild.with_context(context_with_date)).action_unbuild()
            if current_res:  # Prioritize returning an action if one occurred
                res = current_res

        return res if res else True  # Return True if loop finished okay

    # --- Override Move Generation Helper ---
    def _generate_moves(self):
        """
        Override the helper method that creates the stock moves
        to inject our ths_effective_date into the move values.
        """
        self.ensure_one()
        # Get the standard move values prepared by Odoo
        vals_list = super(StockUnbuild, self)._generate_moves()

        # Inject our effective date into the values BEFORE creation
        # Ensure compute method has run for self
        self._compute_ths_effective_date()
        final_date_to_use = self.ths_effective_date

        if final_date_to_use:
            _logger.info(
                f"Unbuild {self.name}: Injecting ths_effective_date {final_date_to_use} into move values during generation.")
            effective_datetime = datetime.combine(final_date_to_use, datetime.min.time())
            for vals in vals_list:
                vals['ths_effective_date'] = final_date_to_use
                vals['date'] = effective_datetime

        return vals_list
