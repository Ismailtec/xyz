# -*- coding: utf-8 -*-

from odoo import models, fields, api

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
			'name', 'encounter_id', 'appointment_id', 'partner_id', 'patient_ids',
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
			entry['patient_ids'] = rec.patient_ids.patient_name('patient_ids')
			result.append(entry)
		return {'data': result, 'fields': fields}

	def _trigger_pos_sync(self, operation='update'):
		"""Trigger POS sync for pending item updates"""
		PosSession = self.env['pos.session']

		if self._name in PosSession.CRITICAL_MODELS:
			try:
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
		""" Override to link items to daily encounters """
		processed_vals_list = []

		for vals in vals_list:
			# Find or create encounter for this item
			if vals.get('partner_id') and not vals.get('encounter_id'):
				partner_id = vals['partner_id']
				encounter_date = fields.Date.context_today(self)

				# Find or create daily encounter
				encounter = self.env['ths.medical.base.encounter']._find_or_create_daily_encounter(
					partner_id, encounter_date
				)
				vals['encounter_id'] = encounter.id

			processed_vals_list.append(vals)

		items = super().create(processed_vals_list)

		# Update encounter payment status
		encounters = items.mapped('encounter_id')
		if encounters:
			encounters._compute_payment_status()

		items._trigger_pos_sync('create')
		return items

	def write(self, vals):
		""" Track state changes to update encounter status """
		# old_states = {item.id: item.state for item in self}
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