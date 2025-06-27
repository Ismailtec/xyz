# -*- coding: utf-8 -*-

from odoo import models


class PosSession(models.Model):
	_inherit = 'pos.session'

	def _loader_params_res_partner(self):
		"""Simple approach: just ensure the field is loaded"""
		params = super()._loader_params_res_partner()

		# Debug: Show current fields
		print(f"Current partner fields: {params['search_params']['fields']}")

		# Check if ths_partner_type_id field exists
		partner_model = self.env['res.partner']
		if 'ths_partner_type_id' in partner_model._fields:
			# Add the field to loading
			if 'ths_partner_type_id' not in params['search_params']['fields']:
				params['search_params']['fields'].append('ths_partner_type_id')
				print(f"✓ Added ths_partner_type_id to partner loading")
		else:
			print(f"✗ ths_partner_type_id field not found on res.partner")

		# Add other medical fields if they exist
		medical_fields = ['is_patient', 'ths_pet_owner_id', 'ref', 'mobile']
		for field in medical_fields:
			if field in partner_model._fields and field not in params['search_params']['fields']:
				params['search_params']['fields'].append(field)

		print(f"Final partner fields: {params['search_params']['fields']}")
		return params

	def get_pos_ui_res_partner(self, params):
		"""Override to debug partner loading"""
		partners = super().get_pos_ui_res_partner(params)

		# Debug: Check if ths_partner_type_id is actually loaded
		for partner in partners[:3]:  # Check first 3 partners
			print(f"Partner {partner['name']}: ths_partner_type_id = {partner.get('ths_partner_type_id', 'MISSING')}")

		return partners

	# Simple method to provide encounters for direct loading
	def get_encounters_for_pos_simple(self):
		"""Simple method to get encounters with proper data"""
		try:
			# Use search_read to get encounters with proper Many2one formatting
			encounters = self.env['ths.medical.base.encounter'].search_read([
				('partner_id', '!=', False),
				('state', 'in', ['in_progress', 'done'])
			], [
				'id', 'name', 'encounter_date', 'partner_id',
				'patient_ids', 'practitioner_id', 'room_id', 'state'
			], order='encounter_date desc', limit=50)

			print(f"Loaded {len(encounters)} encounters via simple method")
			if encounters:
				print(f"Sample encounter: {encounters[0]}")

			return encounters
		except Exception as e:
			print(f"Error in get_encounters_for_pos_simple: {e}")
			return []

	# Simple method to get partner types
	def get_partner_types_simple(self):
		"""Simple method to get partner types"""
		try:
			types = self.env['ths.partner.type'].search_read([
				('active', '=', True)
			], ['id', 'name'])

			print(f"Loaded {len(types)} partner types via simple method")
			return types
		except Exception as e:
			print(f"Error in get_partner_types_simple: {e}")
			return []