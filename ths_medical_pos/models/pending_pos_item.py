# -*- coding: utf-8 -*-

from odoo import models, api

import logging

_logger = logging.getLogger(__name__)


class ThsPendingPosItem(models.Model):
	"""  Extending to add pending related fields for POS items.  """

	_inherit = 'ths.pending.pos.item'

	@api.model
	def _load_pos_data_domain(self, data):
		return [('state', '=', 'pending')]

	@api.model
	def _load_pos_data_fields(self, config_id):
		return [
			'name', 'encounter_id', 'partner_id', 'patient_ids',
			'product_id', 'qty', 'price_unit', 'discount', 'practitioner_id',
			'room_id', 'commission_pct', 'state', 'pos_order_line_id'
		]

	@api.model
	def _load_pos_data(self, data):
		domain = self._load_pos_data_domain(data)
		model_fields = self._load_pos_data_fields(None)
		result = []
		for rec in self.search(domain):
			entry = rec.read(model_fields)[0]
			# entry['patient_ids'] = rec.patient_ids.patient_name('patient_ids')
			result.append(entry)
		return {'data': result, 'fields': model_fields}

	def _trigger_pos_sync(self, operation='update'):
		"""Trigger POS sync for updates"""
		# IMPORTANT: Add this guard. If self is empty, there are no records to sync.
		if not self:
			return

		PosSession = self.env['pos.session']

		if self._name in PosSession.CRITICAL_MODELS:
			try:
				active_sessions = PosSession.search([('state', '=', 'opened')])

				current_data = []
				if operation != 'delete':
					fields_to_sync = self._load_pos_data_fields(False)
					current_data = self.read(fields_to_sync)
				else:
					current_data = [{'id': record_id} for record_id in self.ids]

				for session in active_sessions:
					channel = 'pos.sync.channel'  # (self._cr.dbname, 'pos.session', session.id)
					self.env['bus.bus']._sendone(
						channel,
						'critical_update',
						{
							'type': 'critical_update',
							'model': self._name,
							'operation': operation,
							'records': current_data
						}
					)
					_logger.info(f"POS Sync - Data sent to bus for res.partner (action: {operation}, IDs: {self.ids})")
			except Exception as e:
				_logger.error(f"Error triggering POS sync for {self._name} (IDs: {self.ids}): {e}")

	@api.model_create_multi
	def create(self, vals_list):
		""" Override to link items to daily encounters """
		items = super().create(vals_list)

		encounters = items.mapped('encounter_id')
		if encounters:
			encounters._compute_payment_status()

		items._trigger_pos_sync('create')
		return items

	def write(self, vals):
		""" Track state changes to update encounter status """
		result = super().write(vals)

		# If state changed, update encounter payment status
		if 'state' in vals:
			encounters = self.mapped('encounter_id')
			if encounters:
				encounters._compute_payment_status()

		self._trigger_pos_sync('update')
		return result

	def unlink(self):
		"""Override unlink to trigger sync"""
		self._trigger_pos_sync('delete')
		return super().unlink()