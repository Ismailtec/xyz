# -*- coding: utf-8 -*-

from odoo import models, api, _

import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
	"""
	Extension of calendar.event to support medical POS integration
	Minimal extension - only adds the action method to open gantt view
	"""
	_inherit = 'calendar.event'

	@api.model
	def _load_pos_data_domain(self, data):
		return [('appointment_status', 'not in', ['billed', 'cancelled_by_patient', 'cancelled_by_clinic', 'no_show'])]

	@api.model
	def _load_pos_data_fields(self, config_id):
		return [
			'ths_practitioner_id', 'ths_room_id', 'ths_patient_ids',
			'appointment_status', 'ths_check_in_time', 'ths_check_out_time', 'encounter_id'
		]

	@api.model
	def _load_pos_data(self, data):
		domain = self._load_pos_data_domain(data)
		fields = self._load_pos_data_fields(None)
		result = []
		for rec in self.search(domain):
			entry = rec.read(fields)[0]
			entry['ths_patient_ids'] = rec.ths_patient_ids.patient_name('ths_patient_ids')
			result.append(entry)
		return {'data': result, 'fields': fields}

	def _trigger_pos_sync(self, operation='update'):
		"""Trigger POS sync for calendar event updates"""
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

	def action_open_medical_gantt_view(self):
		"""
		Action to open the medical appointments gantt view from POS
		Uses existing gantt view from ths_medical_base module
		"""
		return {
			'name': _('Medical Schedule'),
			'type': 'ir.actions.act_window',
			'res_model': 'calendar.event',
			'views': [(self.env.ref("ths_medical_base.calendar_event_medical_resource_gantt_ths_medical").id, "gantt")],
			'target': 'current',
			'context': {
				'appointment_booking_gantt_show_all_resources': True,
				'active_model': 'appointment.type',
				'default_partner_ids': [],
				'default_appointment_status': 'draft',
				'default_schedule_based_on': 'resources',
			},
			'domain': [('ths_practitioner_id', '!=', False)],  # Only show medical appointments
		}

	def action_open_medical_form_view(self):
		"""
		Action to open appointment form view for editing from POS
		Uses existing form view from ths_medical_base module
		"""
		return {
			'name': _('Edit Medical Appointment'),
			'target': 'new',
			'type': 'ir.actions.act_window',
			'res_model': 'calendar.event',
			'views': [(self.env.ref('ths_medical_base.view_calendar_event_form_inherit_ths_medical').id, 'form')],
			'res_id': self.id,
		}