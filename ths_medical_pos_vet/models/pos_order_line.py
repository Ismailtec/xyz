# -*- coding: utf-8 -*-

from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
	_inherit = 'pos.order.line'


	# For Veterinary medical
	patient_ids = fields.Many2many(
		'res.partner',
		'ths_medical_encounter_patient_rel',
		'encounter_id',
		'patient_id',
		string='Pets',
		domain="[('ths_partner_type_id.name', '=', 'Pet')]",
		help="Patients who received this service."
	)

	ths_pet_owner_id = fields.Many2one(
		'res.partner',
		'ths_pet_owner_id',
		relation='order_id.partner_id',
		string='Pet Owner',
		domain="[('ths_partner_type_id.name', '=', 'Pet Owner')]",
		help="The owner of the pet receiving this service."
	)

	@api.model
	def _load_pos_data_fields(self, config_id):
		"""  Override to include medical-specific fields in POS data export  """
		line_data = super()._load_pos_data_fields(config_id)
		# Add medical-specific fields to the export
		line_data.extend([
			'ths_pet_owner_id',
		])
		return line_data