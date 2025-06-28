# -*- coding: utf-8 -*-

from odoo import models


class PosSession(models.Model):
	_inherit = 'pos.session'

	def _load_pos_data_models(self, config_id):
		"""Override to add medical models to POS loading"""
		models = super()._load_pos_data_models(config_id)

		# Add medical models using the standard Odoo 18 approach
		medical_models = [
			'ths.partner.type',
			'ths.medical.base.encounter',
			'ths.treatment.room',
			'appointment.resource',  # For practitioners and rooms
		]

		# Add medical models to the standard loading list
		for model in medical_models:
			if model not in models:
				models.append(model)

		print(f"POS Models to load (including medical): {models}")
		return models

	# =========================
	# PARTNER TYPE LOADER
	# =========================

	def _loader_params_ths_partner_type(self):
		"""Loader params for partner types"""
		return {
			'search_params': {
				'domain': [('active', '=', True)],
				'fields': ['id', 'name', 'is_patient', 'is_customer'],
			},
		}

	# =========================
	# ENCOUNTER LOADER
	# =========================

	def _loader_params_ths_medical_base_encounter(self):
		"""Loader params for medical encounters"""
		return {
			'search_params': {
				'domain': [
					('partner_id', '!=', False),
					('state', 'in', ['draft', 'in_progress', 'done'])
				],
				'fields': [
					'id', 'name', 'encounter_date', 'partner_id',
					'patient_ids', 'practitioner_id', 'room_id', 'state'
				],
				'order': 'encounter_date desc',
				'limit': 100,
			},
		}

	# =========================
	# APPOINTMENT RESOURCE LOADER
	# =========================

	def _loader_params_appointment_resource(self):
		"""Loader params for appointment resources (practitioners and rooms)"""
		return {
			'search_params': {
				'domain': [
					('active', '=', True),
					('ths_resource_category', 'in', ['practitioner', 'location'])
				],
				'fields': ['id', 'name', 'ths_resource_category'],
			},
		}

	# =========================
	# TREATMENT ROOM LOADER
	# =========================

	def _loader_params_ths_treatment_room(self):
		"""Loader params for treatment rooms"""
		return {
			'search_params': {
				'domain': [('active', '=', True)],
				'fields': ['id', 'name', 'code', 'room_type'],
			},
		}

	def get_pos_ui_ths_medical_base_encounter(self, params):
		"""Enhanced encounter loading with proper patient_ids formatting"""
		encounters = super().get_pos_ui_ths_medical_base_encounter(params)

		# Format patient_ids using the new helper method
		encounter_ids = [enc['id'] for enc in encounters]
		formatted_patients = self.env['ths.medical.base.encounter'].get_formatted_patients_for_encounter_list(
			encounter_ids)

		for encounter in encounters:
			encounter_id = encounter['id']
			encounter['patient_ids'] = formatted_patients.get(encounter_id, [])

		# Also format other Many2one fields properly
		# [Previous formatting code for practitioner_id, room_id, etc.]

		return encounters

	# def _loader_params_vet_pet_membership(self):
	# 	"""Loader params for pet memberships (will be overridden in vet module)"""
	# 	return {
	# 		'search_params': {
	# 			'domain': [],
	# 			'fields': [],
	# 		},
	# 	}

	# NOTE: Removed get_pos_ui_* methods since JavaScript uses direct searchRead calls
	# The frontend handles data formatting independently for better performance

# TODO: Add caching for frequently accessed encounter data
# TODO: Add batch loading optimization for large datasets