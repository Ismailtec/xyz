# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


# import logging # Logger removed

# _logger = logging.getLogger(__name__) # Logger removed

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost):
        """
        Override to add MRP references to the Journal Entry reference,
        after getting base values from ths_base (which sets effective date).
        """
        self.ensure_one()
        # Get the vals from the parent method (which includes ths_base logic)
        vals = super(StockMove, self)._prepare_account_move_vals(
            credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost
        )

        # Build the reference string including MRP links if present
        ref_parts = []
        # Start with existing ref from parent if any (might already have origin/picking)
        existing_ref_base = vals.get('ref', '').split(' (Eff:')[0].strip()  # Get ref before effective date part
        if existing_ref_base and existing_ref_base != f'Move {self.id}':
            ref_parts.append(existing_ref_base)
        elif self.origin:  # Fallback to origin if base ref was just the move ID
            ref_parts.append(self.origin)

        # Add MRP specific links if they exist on the move
        if self.raw_material_production_id:
            ref_parts.append(self.raw_material_production_id.name)
        elif self.production_id:
            ref_parts.append(self.production_id.name)

        # Add other standard links if not already captured (redundancy check)
        if self.picking_id and self.picking_id.name not in ref_parts:
            ref_parts.append(self.picking_id.name)
        if self.scrap_id and self.scrap_id.name not in ref_parts:
            ref_parts.append(self.scrap_id.name)
        if self.is_inventory and "Inventory Adjustment" not in ref_parts:
            ref_parts.append("Inventory Adjustment")

        # Construct the final reference string
        if ref_parts:
            source_ref = " | ".join(sorted(list(set(ref_parts))))  # Sort and unique
        else:
            source_ref = f'Move {self.id}'  # Fallback

        effective_date_str = f" (Eff: {fields.Date.to_string(self.ths_effective_date)})" if self.ths_effective_date else ""
        vals['ref'] = f"{source_ref}{effective_date_str}".strip()
        #vals['ref'] = f"{source_ref}".strip()
        # _logger.info(f"MRP Move {self.id} - Setting JE Ref: {vals['ref']}") # Logger removed

        return vals
