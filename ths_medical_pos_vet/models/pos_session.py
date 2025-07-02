# -*- coding: utf-8 -*-

from odoo import models, api


class PosSession(models.Model):
	_inherit = 'pos.session'

	@api.model
	def _load_pos_data_models(self, config_id):
		"""Add vet-specific models to POS"""
		original_models = super()._load_pos_data_models(config_id)

		medical_models = [
			'ths.species',
			# 'res.partner',
			# 'ths.medical.base.encounter',
			'vet.pet.membership',
			'park.checkin',
		]

		existing_models = [entry['model'] for entry in original_models if 'model' in entry]

		for model_name in medical_models:
			if model_name not in existing_models:
				original_models.append({'model': model_name})

		print(f"POS Vet Models to load : {original_models}")
		return original_models