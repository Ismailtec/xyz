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
				'fields': ['id', 'name', 'is_patient', 'is_employee'],
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
				'domain': [('active', '=', True)],
				'fields': ['id', 'name', 'ths_resource_category'],
			},
		}

	# =========================
	# OVERRIDE RES.PARTNER LOADER TO INCLUDE PARTNER TYPES
	# =========================

	def _loader_params_res_partner(self):
		"""Override to include medical fields"""
		params = super()._loader_params_res_partner()

		# Check what fields exist on res.partner model
		partner_model = self.env['res.partner']
		available_fields = list(partner_model._fields.keys())

		print(f"Available fields on res.partner: {[f for f in available_fields if 'ths' in f or 'partner_type' in f]}")

		# Add medical fields to partner loading (check if they exist first)
		medical_fields = [
			'ths_partner_type_id',
			'is_patient',
			'ths_pet_owner_id',
			'ref',
			'mobile',
			'membership_state',
			'membership_start',
			'membership_stop'
		]

		# Only add fields that actually exist on the model
		existing_medical_fields = [f for f in medical_fields if f in available_fields]
		print(f"Medical fields that exist: {existing_medical_fields}")

		# Extend existing fields
		params['search_params']['fields'].extend(existing_medical_fields)
		# Remove duplicates
		params['search_params']['fields'] = list(set(params['search_params']['fields']))

		print(f"Final partner fields to load: {params['search_params']['fields']}")
		return params

	# =========================
	# CUSTOM DATA LOADING METHODS
	# =========================

	def get_pos_ui_ths_partner_type(self, params):
		"""Load partner types for POS"""
		return self.env['ths.partner.type'].search_read(**params['search_params'])

	def get_pos_ui_appointment_resource(self, params):
		"""Load appointment resources for POS"""
		return self.env['appointment.resource'].search_read(**params['search_params'])

	def get_pos_ui_ths_medical_base_encounter(self, params):
		"""Load encounters with properly formatted data"""
		# Get encounters using search_read with proper field formatting
		encounters = self.env['ths.medical.base.encounter'].search_read(**params['search_params'])

		# Manually format Many2one and Many2many fields to [id, name] format
		for encounter in encounters:
			# Format partner_id (Many2one)
			if encounter.get('partner_id'):
				if isinstance(encounter['partner_id'], (list, tuple)) and len(encounter['partner_id']) >= 2:
					# Already in [id, name] format, keep as is
					pass
				else:
					# Raw ID, convert to [id, name]
					partner_id = encounter['partner_id']
					partner = self.env['res.partner'].browse(partner_id)
					encounter['partner_id'] = [partner.id, partner.name] if partner.exists() else False

			# Format practitioner_id (Many2one to appointment.resource)
			if encounter.get('practitioner_id'):
				if isinstance(encounter['practitioner_id'], (list, tuple)) and len(encounter['practitioner_id']) >= 2:
					pass
				else:
					practitioner_id = encounter['practitioner_id']
					practitioner = self.env['appointment.resource'].browse(practitioner_id)
					encounter['practitioner_id'] = [practitioner.id,
					                                practitioner.name] if practitioner.exists() else False

			# Format room_id (Many2one to appointment.resource)
			if encounter.get('room_id'):
				if isinstance(encounter['room_id'], (list, tuple)) and len(encounter['room_id']) >= 2:
					pass
				else:
					room_id = encounter['room_id']
					room = self.env['appointment.resource'].browse(room_id)
					encounter['room_id'] = [room.id, room.name] if room.exists() else False

			# Format patient_ids (Many2many to res.partner)
			if encounter.get('patient_ids'):
				if encounter['patient_ids'] and isinstance(encounter['patient_ids'][0], (int)):
					# Raw IDs like [50, 51], convert to [[50, "Name"], [51, "Name"]]
					patient_ids = encounter['patient_ids']
					patients = self.env['res.partner'].browse(patient_ids)
					encounter['patient_ids'] = [[p.id, p.name] for p in patients if p.exists()]
			# If already in correct format, keep as is

		print(f"Loaded {len(encounters)} encounters with formatted data")
		return encounters

	def get_pos_ui_res_partner(self, params):
		"""Override to ensure partner type data is loaded correctly"""
		partners = self.env['res.partner'].search_read(**params['search_params'])

		# Ensure partner type data is properly formatted
		for partner in partners:
			if partner.get('ths_partner_type_id'):
				if isinstance(partner['ths_partner_type_id'], (list, tuple)) and len(
						partner['ths_partner_type_id']) >= 2:
					# Already in [id, name] format
					pass
				else:
					# Raw ID, convert to [id, name]
					type_id = partner['ths_partner_type_id']
					partner_type = self.env['ths.partner.type'].browse(type_id)
					partner['ths_partner_type_id'] = [partner_type.id,
					                                  partner_type.name] if partner_type.exists() else False

		print(f"Loaded {len(partners)} partners with partner type data")
		return partners