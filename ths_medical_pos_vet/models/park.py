# -*- coding: utf-8 -*-

from odoo import models, api


class ParkCheckin(models.Model):
	_name = 'park.checkin'

	@api.model
	def _load_pos_data_domain(self, data):
		return []

	@api.model
	def _load_pos_data_fields(self, config_id):
		return [
			'name', 'partner_id', 'patient_ids', 'checkin_time', 'checkout_time',
			'duration_hours', 'encounter_id', 'membership_valid', 'state'
		]

	@api.model
	def _load_pos_data(self, data):
		fields = self._load_pos_data_fields(None)
		result = []
		for rec in self.search([]):
			entry = rec.read(fields)[0]
			entry['patient_ids'] = rec.patient_ids.patient_name('patient_ids')
			result.append(entry)
		return {'data': result, 'fields': fields}