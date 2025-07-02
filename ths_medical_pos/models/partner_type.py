# -*- coding: utf-8 -*-

from odoo import models, api


class ThsPartnerType(models.Model):
	_inherit = 'ths.partner.type'

	@api.model
	def _load_pos_data_domain(self, data):
		"""Domain for loading partner types in POS"""
		return [('active', '=', True)]

	@api.model
	def _load_pos_data_fields(self, config_id):
		"""Fields to load for partner types in POS"""
		return ['id', 'name', 'is_patient', 'is_employee', 'is_customer', 'is_company', 'is_individual']

	@api.model
	def _load_pos_data(self, data):
		"""Load partner types data for POS"""
		domain = self._load_pos_data_domain(data)
		fields = self._load_pos_data_fields(data.get('pos.config', {}).get('data', [{}])[0].get('id'))
		return {
			'data': self.search_read(domain, fields, load=False),
			'fields': fields
		}