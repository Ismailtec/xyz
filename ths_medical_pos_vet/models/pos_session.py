# -*- coding: utf-8 -*-

from odoo import models, api


class PosSession(models.Model):
	_inherit = 'pos.session'

	@api.model
	def _load_pos_data_models(self, config_id):
		"""Add vet-specific models to POS with tier classification"""
		original_models = super()._load_pos_data_models(config_id)

		# Define vet-specific model tiers
		vet_critical_models = ['vet.pet.membership', 'park.checkin']
		vet_periodic_models = ['ths.species']
		vet_static_models = []

		# Combine all vet models
		all_vet_models = vet_critical_models + vet_periodic_models + vet_static_models

		existing_models = [entry['model'] for entry in original_models if 'model' in entry]

		for model_name in all_vet_models:
			if model_name not in existing_models:
				model_entry = {'model': model_name}

				# Add tier classification for frontend
				if model_name in vet_critical_models:
					model_entry['sync_type'] = 'bus'
				elif model_name in vet_periodic_models:
					model_entry['sync_type'] = 'periodic'
				else:
					model_entry['sync_type'] = 'static'

				original_models.append(model_entry)

		# FIXED: Extend the parent class tier definitions properly
		parent_critical = getattr(self.__class__.__bases__[0], 'CRITICAL_MODELS', [])
		parent_periodic = getattr(self.__class__.__bases__[0], 'PERIODIC_MODELS', [])
		self.CRITICAL_MODELS = parent_critical + vet_critical_models
		self.PERIODIC_MODELS = parent_periodic + vet_periodic_models

		return original_models