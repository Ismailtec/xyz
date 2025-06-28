# -*- coding: utf-8 -*-

from odoo import models


class PosSession(models.Model):
	_inherit = 'pos.session'

	def _loader_params_res_partner(self):
		""" Inherit to add vet-specific fields to partner data loaded in POS """
		params = super()._loader_params_res_partner()
		fields_to_load = params['search_params']['fields']

		# Add vet-specific fields needed for selection, display, and owner linking
		vet_fields = [
			'ths_partner_type_id',
			'ths_pet_owner_id',  # Needed to link Pet -> Owner
			'ths_species_id',  # For pet species display
			'ths_breed_id',  # For pet breed information
			'membership_state',  # From membership module
			'membership_start',  # Membership dates
			'membership_stop',
			'is_pet',  # Computed flag for pets
			'is_pet_owner',  # Computed flag for pet owners
		]

		# Only add fields that exist on the model
		partner_model = self.env['res.partner']
		available_fields = list(partner_model._fields.keys())
		existing_vet_fields = [f for f in vet_fields if f in available_fields]

		fields_to_load.extend(existing_vet_fields)
		# Ensure unique fields
		params['search_params']['fields'] = list(set(fields_to_load))

		print(f"Vet POS: Loading partner fields: {existing_vet_fields}")
		return params

	def _loader_params_ths_medical_base_encounter(self):
		"""Override to add vet-specific encounter fields"""
		params = super()._loader_params_ths_medical_base_encounter()

		# Add vet-specific fields
		vet_encounter_fields = ['ths_pet_owner_id']

		# Check if fields exist and add them
		encounter_model = self.env['ths.medical.base.encounter']
		available_fields = list(encounter_model._fields.keys())
		existing_vet_fields = [f for f in vet_encounter_fields if f in available_fields]

		params['search_params']['fields'].extend(existing_vet_fields)
		params['search_params']['fields'] = list(set(params['search_params']['fields']))

		# Update domain to use vet-specific fields
		if 'ths_pet_owner_id' in available_fields:
			params['search_params']['domain'] = [
				('ths_pet_owner_id', '!=', False),  # Use vet-specific field
				('state', 'in', ['draft', 'in_progress', 'done'])
			]

		return params

	def _loader_params_hr_employee(self):
		""" Inherit to add medical fields to employee data loaded in POS """
		params = super()._loader_params_hr_employee()
		fields_to_load = params['search_params']['fields']

		# Add fields needed for filtering practitioners
		medical_fields = [
			'ths_is_medical',
			'resource_id'  # Needed to check if they are bookable resources
		]

		# Check if fields exist
		employee_model = self.env['hr.employee']
		available_fields = list(employee_model._fields.keys())
		existing_medical_fields = [f for f in medical_fields if f in available_fields]

		fields_to_load.extend(existing_medical_fields)
		params['search_params']['fields'] = list(set(fields_to_load))

		# Add domain to only load relevant employees (medical staff with resources)
		base_domain = params['search_params'].get('domain', [])
		if 'ths_is_medical' in available_fields:
			base_domain.extend([
				('resource_id', '!=', False),
				('ths_is_medical', '=', True)
			])
			params['search_params']['domain'] = base_domain

		return params

	def get_pos_ui_ths_medical_base_encounter(self, params):
		"""Override to handle vet-specific encounter formatting"""
		encounters = super().get_pos_ui_ths_medical_base_encounter(params)

		# Add vet-specific context to encounters
		for encounter in encounters:
			# Format ths_pet_owner_id if it exists
			if encounter.get('ths_pet_owner_id'):
				if isinstance(encounter['ths_pet_owner_id'], (list, tuple)) and len(encounter['ths_pet_owner_id']) >= 2:
					pass  # Already formatted
				else:
					owner_id = encounter['ths_pet_owner_id']
					owner = self.env['res.partner'].browse(owner_id)
					encounter['ths_pet_owner_id'] = [owner.id, owner.name] if owner.exists() else False

			# Add vet context flag
			encounter['vet_context'] = {
				'is_veterinary': True,
				'pet_owner_id': encounter.get('ths_pet_owner_id'),
			}

		return encounters

	def get_pos_ui_res_partner(self, params):
		"""Override to handle vet-specific partner formatting"""
		partners = super().get_pos_ui_res_partner(params)

		# Format vet-specific Many2one fields
		for partner in partners:
			# Format ths_pet_owner_id for pets
			if partner.get('ths_pet_owner_id'):
				if isinstance(partner['ths_pet_owner_id'], (list, tuple)) and len(partner['ths_pet_owner_id']) >= 2:
					pass  # Already formatted
				else:
					owner_id = partner['ths_pet_owner_id']
					owner = self.env['res.partner'].browse(owner_id)
					partner['ths_pet_owner_id'] = [owner.id, owner.name] if owner.exists() else False

			# Format ths_species_id for pets
			if partner.get('ths_species_id'):
				if isinstance(partner['ths_species_id'], (list, tuple)) and len(partner['ths_species_id']) >= 2:
					pass  # Already formatted
				else:
					species_id = partner['ths_species_id']
					species = self.env['ths.species'].browse(species_id)
					partner['ths_species_id'] = [species.id, species.name] if species.exists() else False

			# Format ths_breed_id for pets
			if partner.get('ths_breed_id'):
				if isinstance(partner['ths_breed_id'], (list, tuple)) and len(partner['ths_breed_id']) >= 2:
					pass  # Already formatted
				else:
					breed_id = partner['ths_breed_id']
					breed = self.env['ths.breed'].browse(breed_id)
					partner['ths_breed_id'] = [breed.id, breed.name] if breed.exists() else False

		print(f"Vet POS: Loaded {len(partners)} partners with vet-specific formatting")
		return partners