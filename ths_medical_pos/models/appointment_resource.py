# -*- coding: utf-8 -*-

from odoo import models, api


class AppointmentResource(models.Model):
	_inherit = 'appointment.resource'

	@api.model
	def _load_pos_data_domain(self, data):
		"""Domain for loading appointment resources in POS"""
		return [('ths_resource_category', 'in', ['practitioner', 'location']),
		        ('active', '=', True)]

	@api.model
	def _load_pos_data_fields(self, config_id):
		"""Fields to load for appointment resources in POS"""
		return ['id', 'name', 'ths_resource_category', 'ths_department_id', 'ths_treatment_room_id', 'employee_id']

	@api.model
	def _load_pos_data(self, data):
		"""Load appointment resources data for POS"""
		domain = self._load_pos_data_domain(data)
		model_fields = self._load_pos_data_fields(data.get('pos.config', {}).get('data', [{}])[0].get('id'))
		resources = self.search_read(domain, model_fields, load=False)

		return {
			'data': resources,
			'fields': model_fields
		}