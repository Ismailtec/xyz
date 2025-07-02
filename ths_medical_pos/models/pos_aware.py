# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class PosAwareModel(models.AbstractModel):
	_name = 'pos.aware.model'
	_description = 'Abstract model for POS data synchronization'

	def _trigger_pos_sync(self, operation='update'):
		"""Trigger POS sync for critical models only"""
		# Import here to avoid circular imports
		PosSession = self.env['pos.session']

		if self._name in PosSession.CRITICAL_MODELS:
			try:
				# Get all active POS sessions
				active_sessions = PosSession.search([('state', '=', 'opened')])

				# Prepare sync data using the model's own _load_pos_data method
				if hasattr(self, '_load_pos_data'):
					sync_data = self._load_pos_data({})
					# Filter to only the current records
					current_data = [r for r in sync_data.get('data', []) if r.get('id') in self.ids]
				else:
					# Fallback - use basic read
					current_data = self.read()

				# Send notification to all active sessions
				for session in active_sessions:
					channel = (self._cr.dbname, 'pos.session', session.id)
					self.env['bus.bus']._sendone(
						channel,
						{
							'type': 'critical_update',
							'model': self._name,
							'operation': operation,
							'records': current_data if operation != 'delete' else [{'id': record_id} for record_id in
							                                                       self.ids]
						}
					)

				_logger.info(f"POS sync triggered for {self._name}: {operation} on {len(self)} records")

			except Exception as e:
				_logger.error(f"Error triggering POS sync for {self._name}: {e}")

	@api.model_create_multi
	def create(self, vals_list):
		"""Override create to trigger sync"""
		records = super().create(vals_list)
		records._trigger_pos_sync('create')
		return records

	def write(self, vals):
		"""Override write to trigger sync"""
		result = super().write(vals)
		self._trigger_pos_sync('update')
		return result

	def unlink(self):
		"""Override unlink to trigger sync"""
		self._trigger_pos_sync('delete')
		return super().unlink()