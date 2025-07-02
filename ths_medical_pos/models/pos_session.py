# -*- coding: utf-8 -*-

from odoo import models, api, fields

import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
	_inherit = 'pos.session'

	# @api.model
	# def _load_pos_data_models(self, config_id):
	# 	"""Add base medical models to POS"""
	# 	original_models = super()._load_pos_data_models(config_id)
	#
	# 	medical_models = [
	# 		'ths.partner.type',
	# 		'res.partner',
	# 		'ths.medical.base.encounter',
	# 		'ths.treatment.room',
	# 		'appointment.resource',
	# 		'ths.pending.pos.item',
	# 		'calendar.event',
	# 	]
	#
	# 	existing_models = [entry['model'] for entry in original_models if 'model' in entry]
	#
	# 	for model_name in medical_models:
	# 		if model_name not in existing_models:
	# 			original_models.append({'model': model_name})
	#
	# 	print(f"POS Models to load (including medical): {original_models}")
	# 	return original_models

	# Define data tiers for synchronization
	CRITICAL_MODELS = ['res.partner', 'ths.medical.base.encounter', 'ths.pending.pos.item', 'calendar.event']
	PERIODIC_MODELS = ['ths.treatment.room', 'appointment.resource']
	STATIC_MODELS = ['ths.partner.type']

	@api.model
	def _load_pos_data_models(self, config_id):
		"""Add base medical models to POS with tier classification"""
		original_models = super()._load_pos_data_models(config_id)

		# Define data tiers for synchronization
		critical_models = ['res.partner', 'ths.medical.base.encounter', 'ths.pending.pos.item', 'calendar.event']
		periodic_models = ['ths.treatment.room', 'appointment.resource']
		static_models = ['ths.partner.type']

		# Combine all medical models
		all_medical_models = critical_models + periodic_models + static_models

		existing_models = [entry['model'] for entry in original_models if 'model' in entry]

		for model_name in all_medical_models:
			if model_name not in existing_models:
				# Check if model exists before adding
				try:
					model_obj = self.env[model_name]
					if hasattr(model_obj, '_load_pos_data'):
						model_entry = {'model': model_name}

						# Add tier classification for frontend
						if model_name in critical_models:
							model_entry['sync_type'] = 'bus'
						elif model_name in periodic_models:
							model_entry['sync_type'] = 'periodic'
						else:
							model_entry['sync_type'] = 'static'

						original_models.append(model_entry)
						print(f"✅ POS: Added model {model_name}")
					else:
						print(f"❌ POS: Model {model_name} has no _load_pos_data method")
				except Exception as e:
					print(f"❌ POS: Error with model {model_name}: {e}")

		print(f"POS Models to load (base medical): {[m['model'] for m in original_models if 'model' in m]}")
		return original_models

	@api.model
	def sync_periodic_data(self):
		"""Batch sync for periodic models"""
		from datetime import timedelta

		sessions = self.search([('state', '=', 'opened')])
		sync_data = {}

		# Get records modified in last 2 minutes for periodic models
		cutoff_time = fields.Datetime.now() - timedelta(minutes=2)

		for model_name in self.PERIODIC_MODELS:
			try:
				model = self.env[model_name]
				recent_records = model.search([
					('write_date', '>=', cutoff_time)
				])
				if recent_records and hasattr(model, '_load_pos_data'):
					model_data = model._load_pos_data({})
					recent_data = [r for r in model_data.get('data', []) if r.get('id') in recent_records.ids]
					if recent_data:
						sync_data[model_name] = recent_data
			except Exception as e:
				_logger.error(f"Error syncing periodic data for {model_name}: {e}")

		if sync_data:
			# Send batch update via bus to all active POS sessions
			for session in sessions:
				# Use proper Odoo 18 bus channel format
				channel = (self._cr.dbname, 'pos.session', session.id)
				self.env['bus.bus']._sendone(
					channel,
					{'type': 'batch_sync', 'data': sync_data}
				)

		return sync_data

# TODO: Add caching for frequently accessed encounter data
# TODO: Add batch loading optimization for large datasets