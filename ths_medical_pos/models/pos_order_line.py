# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    # Link back to the source pending item
    ths_pending_item_id = fields.Many2one(
        'ths.pending.pos.item',
        string='Source Pending Item',
        readonly=True,
        copy=False,
        help="The pending medical item that generated this POS line."
    )

    # For human medical: patient = customer (same person receiving service and paying)
    ths_patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        readonly=True,
        copy=False,
        domain="[('ths_partner_type_id.is_patient', '=', True)]",
        help="Patient who received this service. This is the same person as the billing customer."
    )

    # Store Provider for commission/reporting
    ths_provider_id = fields.Many2one(
        'hr.employee',
        string='Provider',
        readonly=True,
        copy=False,
        domain="[('ths_is_medical', '=', True)]",
        help="Medical staff member who provided this service/item."
    )

    # Store specific commission rate for this line
    ths_commission_pct = fields.Float(
        string='Commission %',
        digits='Discount',
        readonly=True,
        copy=False,
        help="Specific commission percentage for the provider on this line."
    )

    # --- HUMAN MEDICAL CONSTRAINTS ---
    @api.constrains('ths_patient_id', 'order_id')
    def _check_human_medical_consistency(self):
        """
        For human medical: ensure patient is consistent with order customer
        Patient should be the same as the order's customer
        """
        for line in self:
            if line.ths_patient_id and line.order_id.partner_id:
                # In human medical, patient should be the billing customer
                if line.ths_patient_id != line.order_id.partner_id:
                    # This could be a warning instead of hard error for flexibility
                    _logger.warning(
                        f"POS Line {line.id}: Patient '{line.ths_patient_id.name}' differs from order customer '{line.order_id.partner_id.name}'. "
                        f"These should typically be the same person."
                    )

    # --- ONCHANGE METHODS FOR HUMAN MEDICAL ---
    @api.onchange('ths_pending_item_id')
    def _onchange_pending_item_sync_data(self):
        """
        When pending item is linked, sync relevant data for human medical context
        """
        if self.ths_pending_item_id:
            item = self.ths_pending_item_id

            # For human medical: patient_id = partner_id (same person)
            if item.patient_id:
                self.ths_patient_id = item.patient_id

            # Sync provider and commission
            if item.practitioner_id:
                self.ths_provider_id = item.practitioner_id
            if item.commission_pct:
                self.ths_commission_pct = item.commission_pct

    # @api.onchange('ths_patient_id')
    # def _onchange_patient_check_consistency(self):
    #     """
    #     When patient changes, check consistency with order customer (human medical)
    #     """
    #     if self.ths_patient_id and self.order_id and self.order_id.partner_id:
    #         if self.ths_patient_id != self.order_id.partner_id:
    #             return {
    #                 'warning': {
    #                     'title': _('Patient/Customer Mismatch'),
    #                     'message': _(
    #                         "The patient receiving service ('%s') "
    #                         "should typically be the same as the customer paying ('%s'). "
    #                         "Please verify this is correct.",
    #                         self.ths_patient_id.name,
    #                         self.order_id.partner_id.name
    #                     )
    #                 }
    #             }

    def export_for_ui(self):
        """ Add custom fields to the data sent to the POS UI """
        line_data = super().export_for_ui()

        # Add medical fields for UI processing
        line_data.update({
            'ths_pending_item_id': self.ths_pending_item_id.id,
            'ths_patient_id': self.ths_patient_id.id,
            'ths_provider_id': self.ths_provider_id.id,
            'ths_commission_pct': self.ths_commission_pct,
        })

        return line_data

    # --- HELPER METHODS FOR HUMAN MEDICAL ---
    def _get_medical_context_summary(self):
        """
        Get a summary of medical context for this line (human medical practice)
        """
        self.ensure_one()
        summary_parts = []

        if self.ths_patient_id:
            summary_parts.append(f"Patient: {self.ths_patient_id.name}")

        if self.ths_provider_id:
            summary_parts.append(f"Provider: {self.ths_provider_id.name}")

        if self.ths_commission_pct:
            summary_parts.append(f"Commission: {self.ths_commission_pct}%")

        if self.ths_pending_item_id:
            summary_parts.append(f"From Encounter: {self.ths_pending_item_id.encounter_id.name}")

        return " | ".join(summary_parts) if summary_parts else "No medical context"

    def _validate_human_medical_data(self):
        """
        Validate medical data consistency for human medical practice
        """
        self.ensure_one()
        errors = []
        warnings = []

        # Check patient-customer consistency
        if self.ths_patient_id and self.order_id.partner_id:
            if self.ths_patient_id != self.order_id.partner_id:
                warnings.append(
                    f"Patient '{self.ths_patient_id.name}' differs from order customer '{self.order_id.partner_id.name}'"
                )

        # Check provider is medical staff
        if self.ths_provider_id and not self.ths_provider_id.ths_is_medical:
            errors.append(
                f"Provider '{self.ths_provider_id.name}' is not marked as medical staff"
            )

        # Check commission percentage is reasonable
        if self.ths_commission_pct and (self.ths_commission_pct < 0 or self.ths_commission_pct > 100):
            errors.append(
                f"Commission percentage {self.ths_commission_pct}% is outside valid range (0-100%)"
            )

        return {'errors': errors, 'warnings': warnings}

    # --- REPORTING METHODS ---
    def _get_commission_amount(self):
        """
        Calculate commission amount for this line
        """
        self.ensure_one()
        if self.ths_commission_pct and self.price_subtotal:
            return (self.price_subtotal * self.ths_commission_pct) / 100.0
        return 0.0

    def _get_patient_info_for_reporting(self):
        """
        Get patient information formatted for reporting
        """
        self.ensure_one()
        if not self.ths_patient_id:
            return "No patient assigned"

        patient = self.ths_patient_id
        info_parts = [patient.name]

        if patient.ref:
            info_parts.append(f"File: {patient.ref}")

        if patient.mobile:
            info_parts.append(f"Mobile: {patient.mobile}")

        return " • ".join(info_parts)

    # TODO: Add integration methods for future enhancements
    def _create_commission_line(self):
        """
        Create commission line for this POS line (if commission module is installed)
        """
        # TODO: This would be implemented by ths_medical_commission module
        pass

    def _update_patient_medical_file(self):
        """
        Update patient's medical file with this service information
        """
        # TODO: Future enhancement for medical record integration
        pass
