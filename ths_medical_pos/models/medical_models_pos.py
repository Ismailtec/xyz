# -*- coding: utf-8 -*-

from odoo import models


class ThsPartnerType(models.Model):
	_inherit = 'ths.partner.type'

	def _load_pos_data_domain(self, data):
		"""Domain for loading partner types in POS"""
		return [('active', '=', True)]

	def _load_pos_data_fields(self, config_id):
		"""Fields to load for partner types in POS"""
		return ['id', 'name', 'is_patient', 'is_employee']

	def _load_pos_data(self, data):
		"""Load partner types data for POS"""
		domain = self._load_pos_data_domain(data)
		fields = self._load_pos_data_fields(data.get('pos.config', {}).get('data', [{}])[0].get('id'))
		partner_types = self.search_read(domain, fields, load=False)

		return {
			'data': partner_types,
			'fields': fields
		}


class ThsMedicalBaseEncounter(models.Model):
	_inherit = 'ths.medical.base.encounter'

	def _load_pos_data_domain(self, data):
		"""Domain for loading encounters in POS"""
		return [
			('partner_id', '!=', False),
			('state', 'in', ['draft', 'in_progress', 'done'])
		]

	def _load_pos_data_fields(self, config_id):
		"""Fields to load for encounters in POS"""
		return [
			'id', 'name', 'encounter_date', 'partner_id',
			'patient_ids', 'practitioner_id', 'room_id', 'state'
		]

	def _load_pos_data(self, data):
		"""Load encounters data for POS with proper formatting"""
		domain = self._load_pos_data_domain(data)
		fields = self._load_pos_data_fields(data.get('pos.config', {}).get('data', [{}])[0].get('id'))

		print(f"Loading encounters with domain: {domain}")
		print(f"Loading encounters with fields: {fields}")

		# First try with search_read to see raw data
		encounters_raw = self.search_read(domain, fields, order='encounter_date desc', limit=100)
		print(f"Raw encounter data sample: {encounters_raw[0] if encounters_raw else 'No encounters'}")

		# Use search to get proper object access for Many2one/Many2many formatting
		encounters = self.search(domain, order='encounter_date desc', limit=100)
		print(f"Found {len(encounters)} encounters")

		encounter_data = []

		for encounter in encounters:
			print(f"Processing encounter {encounter.name} (ID: {encounter.id})")
			print(f"  partner_id: {encounter.partner_id} (exists: {bool(encounter.partner_id)})")
			print(f"  practitioner_id: {encounter.practitioner_id} (exists: {bool(encounter.practitioner_id)})")
			print(f"  room_id: {encounter.room_id} (exists: {bool(encounter.room_id)})")
			print(f"  patient_ids: {encounter.patient_ids} (count: {len(encounter.patient_ids)})")

			encounter_dict = {
				'id': encounter.id,
				'name': encounter.name,
				'encounter_date': encounter.encounter_date.strftime('%Y-%m-%d') if encounter.encounter_date else False,
				'state': encounter.state,
				# Properly format Many2one fields as [id, name]
				'partner_id': [encounter.partner_id.id, encounter.partner_id.name] if encounter.partner_id else False,
				'practitioner_id': [encounter.practitioner_id.id,
				                    encounter.practitioner_id.name] if encounter.practitioner_id else False,
				'room_id': [encounter.room_id.id, encounter.room_id.name] if encounter.room_id else False,
				# Properly format Many2many fields as [[id, name], [id, name]]
				'patient_ids': [[p.id, p.name] for p in encounter.patient_ids] if encounter.patient_ids else [],
			}

			print(f"  -> Formatted encounter_dict: {encounter_dict}")
			encounter_data.append(encounter_dict)

		print(f"Returning {len(encounter_data)} formatted encounters")
		return {
			'data': encounter_data,
			'fields': fields
		}


class ThsTreatmentRoom(models.Model):
	_inherit = 'ths.treatment.room'

	def _load_pos_data_domain(self, data):
		"""Domain for loading treatment rooms in POS"""
		return [
			('resource_id', '!=', False),
			('active', '=', True)
		]

	def _load_pos_data_fields(self, config_id):
		"""Fields to load for treatment rooms in POS"""
		return ['id', 'name', 'resource_id']

	def _load_pos_data(self, data):
		"""Load treatment rooms data for POS"""
		domain = self._load_pos_data_domain(data)
		fields = self._load_pos_data_fields(data.get('pos.config', {}).get('data', [{}])[0].get('id'))
		rooms = self.search_read(domain, fields, load=False)

		return {
			'data': rooms,
			'fields': fields
		}


class AppointmentResource(models.Model):
	_inherit = 'appointment.resource'

	def _load_pos_data_domain(self, data):
		"""Domain for loading appointment resources in POS"""
		return [('active', '=', True)]

	def _load_pos_data_fields(self, config_id):
		"""Fields to load for appointment resources in POS"""
		return ['id', 'name', 'ths_resource_category']

	def _load_pos_data(self, data):
		"""Load appointment resources data for POS"""
		domain = self._load_pos_data_domain(data)
		fields = self._load_pos_data_fields(data.get('pos.config', {}).get('data', [{}])[0].get('id'))
		resources = self.search_read(domain, fields, load=False)

		return {
			'data': resources,
			'fields': fields
		}