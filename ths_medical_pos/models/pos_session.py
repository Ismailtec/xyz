# -*- coding: utf-8 -*-

from odoo import models, api


class PosSession(models.Model):
	_inherit = 'pos.session'

	@api.model
	def _load_pos_data_models(self, config_id):
		"""Add base medical models to POS"""
		original_models = super()._load_pos_data_models(config_id)

		medical_models = [
			'ths.partner.type',
			'res.partner',
			'ths.medical.base.encounter',
			'ths.treatment.room',
			'appointment.resource',
			'ths.pending.pos.item',
			'calendar.event',
		]

		existing_models = [entry['model'] for entry in original_models if 'model' in entry]

		for model_name in medical_models:
			if model_name not in existing_models:
				original_models.append({'model': model_name})

		print(f"POS Models to load (including medical): {original_models}")
		return original_models

# TODO: Add caching for frequently accessed encounter data
# TODO: Add batch loading optimization for large datasets