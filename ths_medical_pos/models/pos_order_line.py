# -*- coding: utf-8 -*-

from odoo import models, fields, api

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

	# For medical: patient = customer (same person receiving service and paying)
	patient_ids = fields.Many2many(
		'res.partner',
		'ths_pos_order_line_patient_rel',
		'pos_order_line_id',
		'patient_id',
		string='Patients',
		domain="[('ths_partner_type_id.is_patient', '=', True)]",
		help="Patients who received this service."
	)

	# Store Provider for commission/reporting
	practitioner_id = fields.Many2one(
		'hr.employee',
		string='Provider',
		related='order_id.practitioner_id',
		readonly=True,
		copy=False,
		domain="[('ths_is_medical', '=', True)]",
		help="Medical staff member who provided this service/item."
	)
	room_id = fields.Many2one(
		'ths.treatment.room',
		string='Treatment Room',
		related='order_id.room_id',
		ondelete='set null',
		index=True,
		help="Treatment room associated with this service."
	)

	# Store specific commission rate for this line
	ths_commission_pct = fields.Float(
		string='Commission %',
		digits='Discount',
		readonly=True,
		copy=False,
		help="Specific commission percentage for the provider on this line."
	)

	encounter_id = fields.Many2one(
		'ths.medical.base.encounter',
		string='Daily Encounter',
		related='order_id.encounter_id',
		store=True,
		readonly=True,
		help="Daily encounter this line belongs to"
	)

	# --- MEDICAL CONSTRAINTS ---
	@api.constrains('patient_ids', 'order_id')
	def _check_human_medical_consistency(self):
		"""
		For medical: ensure patient is consistent with order customer
		Patient should be the same as the order's customer
		"""
		for line in self:
			if line.patient_ids and line.order_id.partner_id:
				# In medical, patient should be the billing customer
				if line.patient_ids != line.order_id.partner_id:
					# This could be a warning instead of hard error for flexibility
					_logger.warning(
						f"POS Line {line.id}: Patient '{line.patient_ids.name}' differs from order customer '{line.order_id.partner_id.name}'. "
						f"These should typically be the same person."
					)

	# --- ONCHANGE METHODS FOR MEDICAL ---
	@api.onchange('ths_pending_item_id')
	def _onchange_pending_item_sync_data(self):
		"""  When pending item is linked, sync relevant data for human medical context  """
		if self.ths_pending_item_id:
			item = self.ths_pending_item_id

			# For medical: patient_id = partner_id (same person)
			if item.patient_ids:
				self.ths_patient_id = item.patient_ids

			# Sync provider and commission
			if item.practitioner_id:
				self.practitioner_id = item.practitioner_id
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

	# def export_for_ui(self):
	# 	""" Add custom fields to the data sent to the POS UI """
	# 	line_data = super().export_for_ui()
	#
	# 	# Add medical fields for UI processing
	# 	line_data.update({
	# 		'ths_pending_item_id': self.ths_pending_item_id.id,
	# 		'patient_ids': self.patient_ids.ids,
	# 		'practitioner_id': self.practitioner_id.id,
	# 		'room_id': self.room_id.id,
	# 		'ths_commission_pct': self.ths_commission_pct,
	# 	})
	#
	# 	return line_data

	@api.model
	def _load_pos_data_fields(self, config_id):
		"""  Override to include medical-specific fields in POS data export  """
		line_data = super()._load_pos_data_fields(config_id)
		# Add medical-specific fields to the export
		line_data.extend([
			'ths_pending_item_id', 'patient_ids', 'practitioner_id', 'room_id', 'ths_commission_pct',
			'encounter_id'
		])
		return line_data

	# --- HELPER METHODS FOR MEDICAL ---
	def _get_medical_context_summary(self):
		"""  Get a summary of medical context for this line (medical practice)  """
		self.ensure_one()
		summary_parts = []

		if self.patient_ids:
			summary_parts.append(f"Patient: {self.patient_ids.name}")

		if self.practitioner_id:
			summary_parts.append(f"Provider: {self.practitioner_id.name}")

		if self.room_id:
			summary_parts.append(f"Room: {self.room_id.name}")

		if self.ths_commission_pct:
			summary_parts.append(f"Commission: {self.ths_commission_pct}%")

		if self.ths_pending_item_id:
			summary_parts.append(f"From Encounter: {self.ths_pending_item_id.encounter_id.name}")

		return " | ".join(summary_parts) if summary_parts else "No medical context"

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
		if not self.patient_ids:
			return "No patient assigned"

		patient = self.patient_ids
		info_parts = [patient.name]

		if patient.ref:
			info_parts.append(f"File: {patient.ref}")

		if patient.mobile:
			info_parts.append(f"Mobile: {self.order_id.partner_id.mobile}")

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

	def get_appointment_context_data(self):
		"""Get appointment context data for POS line pre-filling"""
		self.ensure_one()

		# Try to get appointment data from encounter
		if self.encounter_id and self.encounter_id.appointment_ids:
			appointment = self.encounter_id.appointment_ids[0]  # Get first appointment
			return {
				'practitioner_id': appointment.ths_practitioner_id.id if appointment.ths_practitioner_id else False,
				'patient_ids': appointment.ths_patient_ids.ids if appointment.ths_patient_ids else [],
				'appointment_ids': appointment.id,
			}

		return {}

	def apply_appointment_context(self, appointment_data):
		"""Apply appointment context data to POS line"""
		self.ensure_one()

		vals = {}
		if appointment_data.get('practitioner_id'):
			vals['ths_provider_id'] = appointment_data['practitioner_id']

		if appointment_data.get('patient_ids'):
			# For human medical, take first patient
			vals['ths_patient_id'] = appointment_data['patient_ids'][0]

		if vals:
			self.write(vals)

# TODO: Add line-level encounter service classification
# TODO: Implement encounter-based commission calculations
# TODO: Add encounter service bundling validation
# TODO: Implement encounter inventory allocation