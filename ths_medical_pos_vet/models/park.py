# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


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

	def _trigger_pos_sync(self, operation='update'):
		"""Trigger POS sync for park checkin updates"""
		try:
			PosSession = self.env['pos.session']
			active_sessions = PosSession.search([('state', '=', 'opened')])

			if hasattr(self, '_load_pos_data'):
				sync_data = self._load_pos_data({})
				current_data = [r for r in sync_data.get('data', []) if r.get('id') in self.ids]
			else:
				current_data = self.read()

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